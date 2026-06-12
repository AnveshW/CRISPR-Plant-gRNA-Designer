import os
import json
import asyncio
import logging
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

from backend.scraper import CRISPRScraper

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crispr_backend")

# root_path="/sharp" tells FastAPI/uvicorn that the app is served under /sharp
# The reverse proxy strips /sharp before forwarding — if it does NOT strip it,
# pass --root-path /sharp to uvicorn instead and remove it here.
app = FastAPI(
    title="CRISPR Plant gRNA Designer API",
    description="Backend API services for modern plant genome CRISPR analysis",
    root_path="/sharp"
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache genomes list
GENOMES_CACHE = []

# Resolve Gemini API Key from environment or secrets.toml
def get_gemini_api_key() -> Optional[str]:
    # 1. Environment Variable
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key
    
    # 2. Local secrets.toml paths (Streamlit standard)
    secrets_paths = [
        os.path.join(".streamlit", "secrets.toml"),
        os.path.join("secrets", "secrets.toml"),
        "secrets.toml"
    ]
    for path in secrets_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    for line in f:
                        if "GEMINI_API_KEY" in line:
                            # Extract value between quotes
                            parts = line.split("=")
                            if len(parts) >= 2:
                                val = parts[1].strip().strip('"').strip("'")
                                if val:
                                    return val
            except Exception as e:
                logger.warning(f"Error reading secrets at {path}: {e}")
    return None

# Pydantic Schemas
class AnalyzeRequest(BaseModel):
    selected_genome: str
    input_type: str
    locus_tag: Optional[str] = None
    sequence: Optional[str] = None
    position: Optional[str] = None
    pam: str
    guide_length: str
    promoter: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    summary: str
    user_key: Optional[str] = None  # Allow users to pass key in frontend if not configured on server

@app.get("/api/genomes")
async def get_genomes():
    """Fetches list of plant genomes from CRISPR-PLANT or returns cache."""
    global GENOMES_CACHE
    if GENOMES_CACHE:
        return {"genomes": GENOMES_CACHE}
    
    try:
        scraper = CRISPRScraper()
        genomes = scraper.fetch_genomes()
        GENOMES_CACHE = genomes
        return {"genomes": genomes}
    except Exception as e:
        logger.error(f"Genome loading failure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Submits a job to CRISPR-PLANT and streams logs/results in real-time.
    Uses SSE (Server-Sent Events) style StreamingResponse.
    """
    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def sync_callback(msg: str):
            # Safe call to schedule message insertion on main event loop
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "log", "message": msg})

        # Run scraper in thread pool executor to prevent blocking async loop
        async def run_scraper_task():
            try:
                scraper = CRISPRScraper(progress_callback=sync_callback)
                # Map inputs
                locus = req.locus_tag if req.input_type == "Locus Tag" else None
                seq = req.sequence if req.input_type == "Sequence" else None
                pos = req.position if req.input_type == "Genomic Position" else None

                results = await loop.run_in_executor(
                    None,
                    scraper.run_design_pipeline,
                    req.selected_genome, locus, seq, pos, req.pam, req.guide_length, req.promoter
                )
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "complete", "results": results})
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(e)})

        # Fire and forget scraper task
        asyncio.create_task(run_scraper_task())

        # Stream queue contents to client
        while True:
            item = await queue.get()
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ["complete", "error"]:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/papers")
async def search_papers(query: str, per_page: int = 5):
    """Queries OpenAlex API for research papers."""
    BASE_URL = 'https://api.openalex.org/'
    endpoint = 'works'
    try:
        # Search parameters
        params = {
            'filter': f'title.search:"{query}" OR abstract.search:"{query}"',
            'per_page': per_page,
            'mailto': 'user@example.com'
        }
        res = requests.get(BASE_URL + endpoint, params=params, timeout=10)
        res.raise_for_status()
        results = res.json().get('results', [])
        
        if not results:
            # Fallback broader search
            params = {'search': query, 'per_page': per_page, 'mailto': 'user@example.com'}
            res = requests.get(BASE_URL + endpoint, params=params, timeout=10)
            res.raise_for_status()
            results = res.json().get('results', [])

        # Parse & Format
        papers = []
        for paper in results:
            title = paper.get('title', 'Untitled')
            authors = paper.get('authorships', [])
            author_names = [a.get('author', {}).get('display_name', 'Unknown') for a in authors[:3]]
            author_str = ', '.join(author_names)
            if len(authors) > 3:
                author_str += " et al."
            
            # Abstract reconstruct from inverted index
            abstract_text = ''
            try:
                abstract_inverted = paper.get('abstract_inverted_index')
                if abstract_inverted and isinstance(abstract_inverted, dict):
                    pos_map = {}
                    for word, positions in abstract_inverted.items():
                        for pos in positions:
                            pos_map[pos] = word
                    abstract_text = ' '.join([pos_map[i] for i in sorted(pos_map.keys())])
            except Exception:
                pass

            venue = ""
            if paper.get('primary_location') and paper['primary_location'].get('source'):
                venue = paper['primary_location']['source'].get('display_name', '')

            papers.append({
                'title': title,
                'authors': author_str,
                'year': paper.get('publication_year', 'N/A'),
                'citations': paper.get('cited_by_count', 0),
                'doi': paper.get('doi', ''),
                'url': paper.get('doi') or paper.get('id') or '#',
                'abstract': abstract_text,
                'venue': venue,
                'type': paper.get('type', 'Unknown'),
                'keywords': [kw.get('keyword', '') for kw in paper.get('keywords', [])[:5]],
                'open_access': paper.get('open_access', {}).get('is_oa', False)
            })
            
        return {"papers": papers}
    except Exception as e:
        logger.error(f"Paper search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Debug endpoint to verify the backend is reachable through the HPC proxy."""
    api_key = get_gemini_api_key()
    return {
        "status": "ok",
        "gemini_key_configured": bool(api_key),
        "gemini_key_prefix": api_key[:8] + "..." if api_key else None,
    }

@app.post("/api/chat")
async def chat_assistant(req: ChatRequest):
    """
    Chats with Gemini API regarding CRISPR design results.
    Uses SSE streaming to keep the HPC reverse-proxy connection alive
    and prevent 502 gateway timeouts.
    """
    # Find api key: check user payload first, then server environment/secrets
    api_key = req.user_key or get_gemini_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="Gemini API Key is not configured on the server. Please enter your API key in the chat settings.")

    async def stream_chat():
        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            # Detect if the last user message is a casual/non-technical query
            last_user_msg = next(
                (m.content for m in reversed(req.messages) if m.role == "user"), ""
            )

            CASUAL_PHRASES = {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "bye", "good morning", "good afternoon"}
            is_casual = last_user_msg.strip().lower().rstrip("!.") in CASUAL_PHRASES

            if is_casual:
                system_prompt = (
                    "You are a helpful CRISPR/Cas9 gRNA design assistant. "
                    "Respond naturally, politely, and briefly (1 sentence) to casual greetings or pleasantries."
                )
            else:
                system_prompt = f"""You are an expert CRISPR/Cas9 gRNA design assistant with deep knowledge of plant biotechnology and genome editing.

You are analyzing a set of designed plant guide RNAs. Here is the context of their analysis:
{req.summary}

RESPONSE STYLE & BEHAVIOR:
1. For casual conversational comments, respond briefly and naturally (1 sentence).
2. Only provide detailed, rigorous scientific analysis when responding to a specific query about gRNA candidates, off-target risks, or design parameters.

IMPORTANT GUIDANCE:
1. Do NOT be biased toward any particular gRNA - any candidate could be best depending on the user's experimental goals.
2. Emphasize thorough literature review before final gRNA selection.
3. Rankings in the grid are for logical organization based on general criteria, NOT definitive indicators of the absolute best gRNA.
4. Encourage users to evaluate which critical off-target genes are important for their research.
Be concise (2-3 paragraphs maximum for scientific answers). Keep it highly scientific, precise, and practical."""

            # Format history for Gemini SDK
            conversation = [f"System Instructions:\n{system_prompt}"]
            for msg in req.messages:
                role_label = "User" if msg.role == "user" else "Assistant"
                conversation.append(f"{role_label}: {msg.content}")

            prompt_text = "\n\n".join(conversation)

            # Send initial heartbeat immediately
            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

            # Launch Gemini call in background thread
            from google.genai import types as genai_types

            def _call_gemini():
                return client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt_text,
                    config=genai_types.GenerateContentConfig(
                        thinking_config=genai_types.ThinkingConfig(
                            thinking_budget=1024
                        )
                    )
                )

            gemini_task = asyncio.ensure_future(asyncio.to_thread(_call_gemini))

            # Send heartbeats every 10s while waiting for the Gemini response
            # This keeps the HPC reverse-proxy connection alive
            HEARTBEAT_INTERVAL = 10  # seconds
            TOTAL_TIMEOUT = 300      # seconds
            elapsed = 0

            while not gemini_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(gemini_task), timeout=HEARTBEAT_INTERVAL)
                except asyncio.TimeoutError:
                    pass  # expected — just send another heartbeat
                elapsed += HEARTBEAT_INTERVAL
                if not gemini_task.done():
                    if elapsed >= TOTAL_TIMEOUT:
                        gemini_task.cancel()
                        yield f"data: {json.dumps({'type': 'error', 'message': 'The AI assistant timed out (300s). Please try a simpler or shorter question.'})}\n\n"
                        return
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

            response = gemini_task.result()
            yield f"data: {json.dumps({'type': 'response', 'text': response.text})}\n\n"

        except asyncio.CancelledError:
            logger.error("Gemini API task was cancelled")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Request was cancelled.'})}\n\n"
        except Exception as e:
            logger.error(f"Gemini API failure: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Gemini API Error: {str(e)}'})}\n\n"

    return StreamingResponse(stream_chat(), media_type="text/event-stream")

# Mount static frontend at "/" — root_path="/sharp" on the FastAPI app
# already tells the framework the app lives under /sharp.
# Do NOT mount at "/sharp" here — that would create a double-prefix /sharp/sharp.
frontend_path = os.path.abspath("frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    logger.warning(f"Frontend folder not found at {frontend_path}. Serving API only.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
