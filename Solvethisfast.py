import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import time
import tempfile
import requests
import json
import os
import google.generativeai as genai

# --- Page Configuration ---
st.set_page_config(
    page_title="CRISPR gRNA Analysis Tool",
    page_icon="🔬",
    layout="wide"
)

# ============================================================
# --- Selenium WebDriver Setup ---
# ============================================================
def get_driver():
    """Creates a fresh Selenium WebDriver instance with extended timeouts."""
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-allow-origins=*")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("detach", True)
        user_data_dir = tempfile.mkdtemp()
        options.add_argument(f"--user-data-dir={user_data_dir}")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(600)
        driver.set_script_timeout(600)
        driver.command_executor.set_timeout(600)
        return driver
    except Exception as e:
        st.error(f"Failed to initialize Chrome driver: {e}")
        return None


# ============================================================
# --- Helper Functions ---
# ============================================================
def get_available_genomes(driver):
    """Fetches all available genomes from the dropdown on the CRISPR-PLANT site."""
    try:
        wait = WebDriverWait(driver, 30)
        dropdown = wait.until(EC.presence_of_element_located((By.ID, "name_db")))
        options = dropdown.find_elements(By.TAG_NAME, "option")
        genomes = [opt.text.strip() for opt in options if opt.text.strip()]
        return genomes
    except TimeoutException:
        st.error("Timeout waiting for genome dropdown to load.")
        return []
    except Exception as e:
        st.error(f"Error fetching genomes: {e}")
        return []


def find_results_table(driver):
    """Find the correct results table by looking for the table with gRNA data."""
    try:
        wait = WebDriverWait(driver, 180)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        all_tables = driver.find_elements(By.TAG_NAME, "table")

        if 'status' in st.session_state:
            st.session_state.status.update(label=f"Found {len(all_tables)} table(s) on page. Searching for results table...")

        for table in all_tables:
            try:
                table_html = table.get_attribute("outerHTML").lower()
                if any(keyword in table_html for keyword in ['guide', 'score', 'sequence', 'region']):
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    if len(rows) >= 2:
                        first_row_text = rows[0].text.lower()
                        if any(col in first_row_text for col in ['score', 'sequence', 'region', 'gc']):
                            if 'status' in st.session_state:
                                st.session_state.status.update(label=f"Found results table with {len(rows)} rows.")
                            return table
            except:
                continue

        max_rows = 0
        results_table = None
        for table in all_tables:
            try:
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) > max_rows and len(rows) >= 3:
                    if rows[1].find_elements(By.TAG_NAME, "td"):
                        max_rows = len(rows)
                        results_table = table
            except:
                continue

        if results_table:
            if 'status' in st.session_state:
                st.session_state.status.update(label=f"Selected table with {max_rows} rows as results table.")
            return results_table

        for table in all_tables:
            try:
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) >= 2:
                    first_data_row = rows[1] if len(rows) > 1 else rows[0]
                    cells = first_data_row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 3:
                        return table
            except:
                continue

        raise NoSuchElementException("Could not identify the results table among available tables.")

    except TimeoutException:
        raise TimeoutException("Timeout waiting for tables to load on results page.")
    except Exception as e:
        raise Exception(f"Error finding results table: {str(e)}")


def get_off_target_data_by_interaction(driver, grna_element):
    """Get off-target data by hovering/clicking on gRNA sequence."""
    try:
        actions = ActionChains(driver)
        actions.move_to_element(grna_element).perform()
        time.sleep(2)
        try:
            grna_element.click()
            time.sleep(2)
        except:
            pass

        off_target_tables = driver.find_elements(By.XPATH, "//table[contains(@class, 'offTarget') or contains(@id, 'offTarget')]")
        if not off_target_tables:
            all_tables = driver.find_elements(By.TAG_NAME, "table")
            for table in all_tables:
                table_text = table.text.lower()
                if 'off' in table_text or 'target' in table_text or 'gene' in table_text:
                    off_target_tables = [table]
                    break

        if not off_target_tables:
            return []

        off_target_data = []
        table = off_target_tables[0]
        rows = table.find_elements(By.TAG_NAME, "tr")
        headers = []

        if rows:
            header_cells = rows[0].find_elements(By.TAG_NAME, "th")
            if not header_cells:
                header_cells = rows[0].find_elements(By.TAG_NAME, "td")
            headers = [cell.text.strip().lower() for cell in header_cells]

        sequence_col = region_col = gene_col = score_col = -1
        for i, header in enumerate(headers):
            if 'sequence' in header or 'seq' in header:
                sequence_col = i
            elif 'region' in header:
                region_col = i
            elif 'gene' in header:
                gene_col = i
            elif 'score' in header or 'off' in header:
                score_col = i

        for row in rows[1:]:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) > 0:
                sequence = cells[sequence_col].text.strip() if sequence_col >= 0 and sequence_col < len(cells) else ""
                region = cells[region_col].text.strip() if region_col >= 0 and region_col < len(cells) else ""
                gene = cells[gene_col].text.strip() if gene_col >= 0 and gene_col < len(cells) else ""
                score = cells[score_col].text.strip() if score_col >= 0 and score_col < len(cells) else ""

                if not sequence:
                    for cell in cells:
                        text = cell.text.strip()
                        if len(text) >= 15 and all(c.upper() in 'ATCG-' for c in text if c.isalpha()):
                            sequence = text
                            break

                if sequence:
                    off_target_data.append({
                        'sequence': sequence,
                        'region': region.lower(),
                        'gene': gene,
                        'score': score
                    })
        return off_target_data
    except Exception:
        return []


def submit_crispr_plant_job(driver, selected_genome, locus_tag, sequence, position,
                             pam, pam_map, guide_length, promoter, status_label=None):
    """
    Navigates to CRISPR-PLANT, fills the form with user inputs, and submits.
    Shared by both the main run and the Load All run.
    """
    if status_label and 'status' in st.session_state:
        st.session_state.status.update(label=status_label)

    driver.get("http://crispr.hzau.edu.cn/cgi-bin/CRISPR2/CRISPR")
    time.sleep(5)

    wait = WebDriverWait(driver, 30)
    start_link = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Start")))
    start_link.click()
    time.sleep(3)

    dropdown = wait.until(EC.presence_of_element_located((By.ID, "name_db")))
    dropdown.find_element(By.XPATH, f"//option[. = '{selected_genome}']").click()
    time.sleep(1)

    pam_dropdown = wait.until(EC.presence_of_element_located((By.ID, "pppp")))
    Select(pam_dropdown).select_by_index(pam_map.get(pam, 0))
    time.sleep(0.5)

    guide_length_numeric = guide_length.split()[0]
    guide_length_dropdown = wait.until(EC.presence_of_element_located((By.ID, "spacer_length")))
    try:
        Select(guide_length_dropdown).select_by_value(guide_length_numeric)
    except:
        guide_length_index = int(guide_length_numeric) - 15
        Select(guide_length_dropdown).select_by_index(guide_length_index)
    time.sleep(0.5)

    if promoter == "U6":
        driver.find_element(By.CSS_SELECTOR, "label:nth-child(1) > #ppp").click()
    else:
        driver.find_element(By.CSS_SELECTOR, "label:nth-child(2) > #ppp").click()
    time.sleep(0.5)

    if locus_tag:
        locus_input = wait.until(EC.presence_of_element_located((By.ID, "loc_search")))
        locus_input.clear()
        locus_input.send_keys(locus_tag)
    elif sequence:
        sequence_input = wait.until(EC.presence_of_element_located((By.ID, "sequenceid")))
        sequence_input.clear()
        sequence_input.send_keys(sequence)
    elif position:
        position_input = wait.until(EC.presence_of_element_located((By.ID, "position")))
        position_input.clear()
        position_input.send_keys(position)

    submit_button = wait.until(EC.element_to_be_clickable((By.NAME, ".submit")))
    submit_button.click()
    time.sleep(20)


def analyze_crispr_results(driver):
    """
    Standard analysis — parses all gRNAs, applies quality filters, picks TOP 30,
    runs off-target interaction on those 30, then re-ranks them.
    This is the ORIGINAL fast analysis. Completely unchanged.
    """
    try:
        main_table = find_results_table(driver)
        rows = main_table.find_elements(By.TAG_NAME, "tr")

        if len(rows) < 2:
            raise ValueError("No gRNA results found in the table. The locus tag may not exist or produced no results.")

        if 'status' in st.session_state:
            st.session_state.status.update(label=f"Parsing {len(rows)-1} gRNA results from table...")

        grna_data = []
        for i, row in enumerate(rows[1:], 1):
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 3:
                cell_texts = [cell.text.strip() for cell in cells]
                grna_element = None
                grna_sequence = ""
                score = 0.0
                gc_content = 0.0
                region = ""

                for j, cell in enumerate(cells):
                    text = cell.text.strip()
                    if len(text) >= 20 and len(text) <= 25 and all(c.upper() in 'ATCG' for c in text if c.isalpha()):
                        grna_sequence = text
                        grna_element = cell
                        break

                for text in cell_texts:
                    try:
                        val = float(text)
                        if 0.0 <= val <= 1.0 and '.' in text:
                            score = val
                            break
                    except ValueError:
                        pass

                for text in cell_texts:
                    if '%' in text:
                        try:
                            gc_content = float(text.replace('%', ''))
                            break
                        except ValueError:
                            pass

                for text in cell_texts:
                    text_lower = text.lower()
                    if text_lower in ['exon', 'utr', 'intron', 'cds', "5'utr", "3'utr"]:
                        region = text_lower
                        break

                if grna_sequence and grna_element:
                    grna_data.append({
                        'index': i,
                        'sequence': grna_sequence,
                        'score': score,
                        'gc_content': gc_content,
                        'region': region,
                        'element': grna_element
                    })

        if len(grna_data) == 0:
            raise ValueError("No valid gRNA sequences found in the results. The locus tag may be invalid for this genome.")

        if 'status' in st.session_state:
            st.session_state.status.update(label=f"Extracted {len(grna_data)} total gRNAs. Starting prioritization...")

        high_score = [g for g in grna_data if g['score'] > 0.0000]
        good_gc = [g for g in high_score if g['gc_content'] > 40.0]

        region_priority = {'exon': 3, 'utr': 2, 'intron': 1, 'cds': 2, "5'utr": 2, "3'utr": 2}

        prioritized_grnas = sorted(
            good_gc,
            key=lambda x: (region_priority.get(x['region'], 0), x['score']),
            reverse=True
        )

        # ---- TOP 30 LIMIT (original behaviour, unchanged) ----
        top_grnas = prioritized_grnas[:30] if len(prioritized_grnas) >= 30 else prioritized_grnas

        if len(top_grnas) == 0:
            raise ValueError("No gRNAs passed quality filters (score > 0.0, GC content > 40%). Try different parameters or locus tag.")

        if 'status' in st.session_state:
            st.session_state.status.update(label=f"Found {len(top_grnas)} high-quality gRNAs. Analyzing off-targets...")

        for idx, grna in enumerate(top_grnas):
            off_targets = get_off_target_data_by_interaction(driver, grna['element'])
            grna['off_targets'] = off_targets
            grna['off_target_count'] = len(off_targets)
            critical_off_targets = [ot for ot in off_targets if ot['region'] in ['exon', 'cds', 'utr']]
            grna['critical_off_targets'] = critical_off_targets
            grna['critical_count'] = len(critical_off_targets)
            if 'status' in st.session_state:
                st.session_state.status.update(label=f"Analyzing off-targets for gRNA {idx + 1}/{len(top_grnas)}...")
            time.sleep(1)

        final_prioritized = sorted(
            top_grnas,
            key=lambda x: (x['critical_count'], x['off_target_count'], -region_priority.get(x['region'], 0), -x['score'])
        )

        return final_prioritized

    except NoSuchElementException as e:
        raise NoSuchElementException(f"Could not find expected elements on results page: {str(e)}")
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Unexpected error during result analysis: {str(e)}")


# ============================================================
# --- OpenAlex API Functions ---
# ============================================================

def search_openalex(query, per_page=5):
    """
    Search OpenAlex API for papers related to a query.
    Tries multiple search strategies to find relevant papers.
    """
    BASE_URL = 'https://api.openalex.org/'
    endpoint = 'works'
    
    try:
        # Strategy 1: Try with quoted search (most precise)
        params = {
            'filter': f'title.search:"{query}" OR abstract.search:"{query}"',
            'per_page': per_page,
            'mailto': 'user@example.com'
        }
        
        response = requests.get(BASE_URL + endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', [])
        
        # If we got results, return them
        if results:
            return results
        
        # Strategy 2: If no results, try simpler search without quotes
        params = {
            'search': query,
            'per_page': per_page,
            'mailto': 'user@example.com'
        }
        
        response = requests.get(BASE_URL + endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', [])
        
        if results:
            return results
        
        # Strategy 3: Try with title or abstract separately
        params = {
            'filter': f'title.search:{query}',
            'per_page': per_page,
            'mailto': 'user@example.com'
        }
        
        response = requests.get(BASE_URL + endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', [])
        
        return results
        
    except Exception as e:
        st.error(f"Error fetching papers: {str(e)}")
        return []


def format_paper_result(paper):
    """
    Format a single OpenAlex paper result for display with detailed information.
    """
    title = paper.get('title', 'No title')
    authors = paper.get('authorships', [])
    author_names = [a.get('author', {}).get('display_name', 'Unknown') for a in authors[:3]]
    author_str = ', '.join(author_names)
    if len(authors) > 3:
        author_str += f" et al."
    
    year = paper.get('publication_year', 'N/A')
    doi = paper.get('doi', '')
    url = paper.get('doi', paper.get('id', '#'))
    citation_count = paper.get('cited_by_count', 0)
    
    # Extract abstract (OpenAlex stores it in abstract_inverted_index format)
    abstract_text = ''
    try:
        abstract_inverted = paper.get('abstract_inverted_index')
        if abstract_inverted and isinstance(abstract_inverted, dict):
            # Reconstruct abstract from inverted index
            # abstract_inverted format: {"word": [0, 5, 12], "another": [1, 8]}
            max_pos = 0
            for positions in abstract_inverted.values():
                if positions:
                    max_pos = max(max_pos, max(positions))
            
            # Create position to word mapping
            position_map = {}
            for word, positions in abstract_inverted.items():
                for pos in positions:
                    position_map[pos] = word
            
            # Build abstract from sorted positions
            abstract_words = [position_map[i] for i in sorted(position_map.keys())]
            abstract_text = ' '.join(abstract_words) if abstract_words else ''
    except Exception as e:
        abstract_text = ''
    
    # Get publication venue (journal name)
    venue = ''
    if paper.get('primary_location') and paper['primary_location'].get('source'):
        venue = paper['primary_location']['source'].get('display_name', '')
    
    # Get publication type
    pub_type = paper.get('type', 'Unknown')
    
    # Get keywords/topics
    keywords = []
    if paper.get('keywords'):
        keywords = [kw.get('keyword', '') for kw in paper['keywords'][:5]]
    
    # Get open access status
    is_open_access = paper.get('open_access', {}).get('is_oa', False)
    
    return {
        'title': title,
        'authors': author_str,
        'year': year,
        'citations': citation_count,
        'url': url,
        'doi': doi,
        'abstract': abstract_text,
        'venue': venue,
        'type': pub_type,
        'keywords': keywords,
        'open_access': is_open_access
    }


def display_paper_details(formatted_paper):
    st.write(f"**Title:** {formatted_paper['title']}")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"**Authors:** {formatted_paper['authors']}")
    with col2:
        st.write(f"**Year:** {formatted_paper['year']}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Citations:** {formatted_paper['citations']}")
    with col2:
        st.write("🔓 **Open Access:** Yes" if formatted_paper['open_access'] else "🔒 **Open Access:** No")
    with col3:
        st.write(f"**Type:** {formatted_paper['type']}")
    if formatted_paper['venue']:
        st.write(f"**Journal/Venue:** {formatted_paper['venue']}")
    if formatted_paper['abstract']:
        with st.expander("📄 Abstract"):
            st.write(formatted_paper['abstract'])
    else:
        st.info("📄 Abstract not available in database please click the doi")
    if formatted_paper['keywords']:
        st.write(f"**Keywords:** {', '.join([k for k in formatted_paper['keywords'] if k])}")
    if formatted_paper['doi']:
        st.write(f"**DOI:** [{formatted_paper['doi']}]({formatted_paper['url']})")
        st.caption("Click on the DOI to access the full paper and abstract on the publisher's website")


# ============================================================
# --- Streamlit App UI ---
# ============================================================
st.title("🔬 CRISPR gRNA Design & Analysis Pipeline")
st.write("This tool automates gRNA design using the CRISPR-PLANT website, then performs a comprehensive off-target analysis to identify the safest and most effective candidates.")

# --- Session State Init ---
if 'genomes_list' not in st.session_state:
    st.session_state.genomes_list = None
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None



# ============================================================
# --- Sidebar ---
# ============================================================
with st.sidebar:
    st.header("1. Input Parameters")

    input_type = st.radio(
        "Input Type",
        options=["Locus Tag", "Sequence", "Genomic Position"],
        help="Choose which type of input you want to provide"
    )

    if input_type == "Locus Tag":
        locus_tag = st.text_input("Locus Tag", "GLYMA14G07880", help="Enter the gene identifier (e.g., AT2G43010)")
        sequence = None
        position = None
    elif input_type == "Sequence":
        locus_tag = None
        sequence = st.text_area("DNA Sequence", "", help="Enter your DNA sequence here (ATCG only)")
        position = None
    else:
        locus_tag = None
        sequence = None
        position = st.text_input("Genomic Position", "", help="e.g., Chr1:12345-12500")

    pam_options = [
        "NGG (SpCas9)", "NAG (SpCas9)", "NGA (SpCas9)",
        "NNGRRT (SaCas9)", "NNNRRT (SaCas9-KKH)",
        "TTTN (Cpf1)", "TTN (Cas12a)", "NG (SpCas9-NG)",
        "NGA (SpCas9-VQR)", "NGCG (SpCas9-VRER)",
        "TTTN (AsCpf1)", "TTTN (LbCpf1)"
    ]
    pam_map = {p: i for i, p in enumerate(pam_options)}

    pam = st.selectbox(
        "PAM Sequence", options=pam_options, index=0,
        help="Select a PAM type. NGG is standard for SpCas9."
    )

    guide_length = st.selectbox(
        "Guide Sequence Length",
        options=["15 bp", "16 bp", "17 bp", "18 bp", "19 bp", "20 bp", "21 bp", "22 bp"],
        index=5,
        help="Select the guide RNA spacer length. Standard is 20 bp for SpCas9."
    )

    promoter = st.radio(
        "snoRNA Promoter",
        options=["U3 (default)", "U6"],
        index=0,
        help="Choose the promoter for plant snoRNA design"
    )

    has_input = any([locus_tag, sequence, position])
    if not has_input:
        st.warning("⚠️ Please provide an input (Locus Tag, Sequence, or Position)")

    st.header("2. Genome Selection")

    if st.button("Fetch Available Genomes"):
        with st.spinner("Connecting to CRISPR-PLANT to get genome list..."):
            driver = get_driver()
            if driver:
                try:
                    driver.get("http://crispr.hzau.edu.cn/cgi-bin/CRISPR2/CRISPR")
                    time.sleep(5)
                    wait = WebDriverWait(driver, 30)
                    start_link = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Start")))
                    start_link.click()
                    time.sleep(3)
                    st.session_state.genomes_list = get_available_genomes(driver)
                except Exception as e:
                    st.error(f"Could not fetch genomes. Error: {e}")
                finally:
                    driver.quit()

    if st.session_state.genomes_list:
        default_index = st.session_state.genomes_list.index("Glycine max (V1.0)") if "Glycine max (V1.0)" in st.session_state.genomes_list else 0
        selected_genome = st.selectbox(
            "Select Genome", st.session_state.genomes_list,
            index=default_index,
            help="Select the target genome from the list fetched from the website."
        )
        st.success(f"{len(st.session_state.genomes_list)} genomes loaded successfully!")
    else:
        selected_genome = None
        st.info("Click 'Fetch Available Genomes' to load the list from the CRISPR-PLANT website.")

    st.header("3. Run Analysis")
    run_button = st.button(
        "🚀 Design and Analyze gRNAs",
        type="primary",
        disabled=(not st.session_state.genomes_list or not has_input)
    )


# ============================================================
# --- Main Run: Top 30 with Off-Target Analysis (ORIGINAL) ---
# ============================================================
if run_button:
    # Reset all states on fresh run
    st.session_state.analysis_result = None

    driver = get_driver()
    if not driver:
        st.error("Failed to initialize web driver. Please try again.")
    else:
        with st.status("Running CRISPR Analysis Pipeline...", expanded=True) as status:
            st.session_state.status = status
            try:
                submit_crispr_plant_job(
                    driver=driver,
                    selected_genome=selected_genome,
                    locus_tag=locus_tag,
                    sequence=sequence,
                    position=position,
                    pam=pam,
                    pam_map=pam_map,
                    guide_length=guide_length,
                    promoter=promoter,
                    status_label="Navigating to CRISPR-PLANT and submitting your job..."
                )
                input_hint = locus_tag or (sequence[:20] + "...") if sequence else position
                status.update(label=f"Job submitted for '{input_hint}'. Waiting for results... (This can take up to a minute)")

                status.update(label="Results received! Parsing and analyzing top 30 gRNAs with off-target analysis...")
                final_results = analyze_crispr_results(driver)
                st.session_state.analysis_result = final_results
                status.update(label="Analysis Complete!", state="complete", expanded=False)

            except TimeoutException as e:
                status.update(label="Timeout error occurred!", state="error")
                st.error(f"⏱️ **Timeout Error**: {str(e)}")
                st.warning(
                    f"**Possible reasons:**\n- The input may not exist in the selected genome\n"
                    f"- The CRISPR server is taking too long to respond\n- Network connectivity issues\n\n"
                    f"**Suggestions:**\n- Verify your input is correct for '{selected_genome}'\n"
                    f"- Try again in a few minutes\n- Try a different input known to work"
                )
            except NoSuchElementException as e:
                status.update(label="Could not find results!", state="error")
                st.error(f"❌ **Element Not Found**: {str(e)}")
                st.warning(
                    f"**Possible reasons:**\n- The input does not exist in '{selected_genome}'\n"
                    f"- The results page structure is different than expected\n\n"
                    f"**Suggestions:**\n- Double-check your input\n"
                    f"- Try a known working tag (e.g., 'GLYMA14G07880' or 'GLYMA13G08120')"
                )
            except ValueError as e:
                status.update(label="No results found!", state="error")
                st.error(f"❌ **No Valid Results**: {str(e)}")
                st.warning("The analysis completed but no valid gRNAs were found that meet the quality criteria.")
            except WebDriverException as e:
                status.update(label="Browser error occurred!", state="error")
                st.error(f"🌐 **Browser Error**: {str(e)}")
                st.warning("The CRISPR-PLANT website may be temporarily unavailable. Please try again later.")
            except Exception as e:
                status.update(label="An error occurred!", state="error")
                st.error(f"⚠️ **Unexpected Error**: {str(e)}")
                st.warning("An unexpected error occurred. Please try again or contact support if the problem persists.")
            finally:
                driver.quit()


# ============================================================
# --- Display Results ---
# ============================================================
if st.session_state.analysis_result:
    st.header("📊 Analysis Results")

    results_data = []
    for grna in st.session_state.analysis_result[:30]:  # Limit to 30 results
        critical_genes = []
        for critical in grna['critical_off_targets']:
            if critical['gene'] and critical['gene'] not in critical_genes:
                critical_genes.append(critical['gene'])
        results_data.append({
            'Sequence': grna['sequence'],
            'GC Content': f"{grna['gc_content']:.1f}%",
            'Region': grna['region'],
            'Critical Off-Targets': grna['critical_count'],
            'Total Off-Targets': grna['off_target_count'],
            'Critical Genes': ', '.join(critical_genes)
        })

    results_df = pd.DataFrame(results_data)
    results_df.insert(0, 'Rank', range(1, len(results_df) + 1))

    st.write(
        f"Found and prioritized **{len(results_df)}** high-quality gRNAs based on: "
        f"on-target score, GC content, genomic region, and off-target analysis."
    )
    st.dataframe(results_df, use_container_width=True)

    # Download button for top-30 table
    csv_top30 = pd.DataFrame(results_data).to_csv(index=False)
    input_label = locus_tag or "results"
    st.download_button(
        label="📥 Download Top 30 Results as CSV",
        data=csv_top30,
        file_name=f"grna_top30_{input_label}.csv",
        mime="text/csv"
    )

    # ============================================================
    # --- Important Recommendation Banner ---
    # ============================================================
    st.markdown("---")
    st.markdown(
        "<div style='margin-bottom: 24px; padding: 16px; background-color: #f9f9f9; color: #222; border-radius: 8px; border: 1px solid #e0e0e0;'>"
        "<b>📋 Important Recommendation:</b><br>"
        "This table contains high-quality gRNAs ranked by their on-target efficiency and specificity scores.<br>"
        "We <b>strongly recommend analyzing every critical off-target gene in detail</b> through genome database searches and literature review before final gRNA selection. "
        "Consider the biological importance of each critical gene and its potential impact on your experimental goals. "
        "Use the <b>Critical Off-Target Genes Research</b> section below to explore papers for each affected gene to make an informed decision."
        "</div>", unsafe_allow_html=True
    )

    # ============================================================
    # --- AI Assistant ---
    # ============================================================
    st.header("🤖 AI Assistant - Ask Questions About Your Results")

    all_grnas_ai = st.session_state.analysis_result[:30]  # Limit to 30 results
    grna_details = []
    for grna in all_grnas_ai:
        critical_genes = [c['gene'] for c in grna['critical_off_targets'] if c['gene']]
        grna_details.append(
            f"Sequence: {grna['sequence']} | Score: {grna['score']:.4f} | GC: {grna['gc_content']:.1f}% | "
            f"Region: {grna['region']} | Critical Off-targets: {grna['critical_count']} | "
            f"Critical Genes: {', '.join(critical_genes) if critical_genes else 'None'}"
        )

    analysis_summary = f"""
Analysis Context:
- Target Gene: {locus_tag or 'User sequence'}
- Genome: {selected_genome or 'Unknown'}
- Total gRNAs Analyzed: {len(st.session_state.analysis_result)}

All gRNA Candidates:
{chr(10).join(grna_details)}

All gRNAs shown are categorized by lowest critical off-target count, then off-target count, then genomic region priority, and finally on-target score. However, this ranking is only for organization purposes. The best gRNA for your specific experiment may be any of these candidates depending on your research goals and the biological significance of the off-target genes involved.
"""

    st.info("💡 Ask me about your gRNA results, off-target effects, or CRISPR design strategies!")

    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'gemini_client' not in st.session_state:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        try:
            genai.configure(api_key=gemini_api_key)
            st.session_state.gemini_client = genai.GenerativeModel('gemini-2.5-flash')
        except Exception as e:
            st.error("⚠️ Unable to initialize AI assistant. Please try again.")
            st.session_state.gemini_client = None

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if st.session_state.gemini_client:
        st.write("**Quick Questions:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📊 How should I choose my best gRNA?"):
                st.session_state.quick_question = "Based on the analysis results, what factors should I consider when choosing between these gRNA candidates? Please explain the key differences and help me understand the trade-offs between targeting efficiency, specificity, and off-target risks."
        with col2:
            if st.button("✅ What makes a good gRNA?"):
                st.session_state.quick_question = "What makes a good gRNA for CRISPR experiments?"
        with col3:
            if st.button("🔬 How to validate experimentally?"):
                st.session_state.quick_question = "How do I validate these gRNAs experimentally in the lab?"

        if prompt := st.chat_input("Ask about your gRNA results..."):
            user_message = prompt
        elif 'quick_question' in st.session_state:
            user_message = st.session_state.quick_question
            del st.session_state.quick_question
        else:
            user_message = None

        if user_message:
            st.session_state.chat_history.append({"role": "user", "content": user_message})
            with st.chat_message("user"):
                st.markdown(user_message)

            system_prompt = f"""You are an expert CRISPR/Cas9 gRNA design assistant with deep knowledge of plant biotechnology and genome editing.

The user has just completed a gRNA analysis. Here are their results:
{analysis_summary}

IMPORTANT GUIDANCE FOR YOU:
1. Do NOT be biased toward any particular gRNA in the list - any of the candidates could be the best choice depending on the user's specific experimental goals
2. Emphasize the critical importance of literature review - repeatedly remind users that thorough literature review of each gRNA candidate is VERY CRUCIAL before final selection
3. Clarify ranking context - explain that these rankings are primarily for organizational purposes and easy design workflows, NOT definitive indicators of the "best" gRNA
4. Consider user-specific factors - encourage users to analyze which critical genes matter most for their research and whether off-targeting them is acceptable
5. Use research paper information to inform your answers - if the user asks about specific genes or off-target effects, use the research paper explorer data to provide insights on the biological significance of those genes and potential consequences of off-targeting them. Also refer to those papers when discussing validation strategies or design trade-offs.

Be specific to their data. Be concise (2-3 paragraphs). Be scientifically accurate. Always emphasize the importance of literature review."""

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                try:
                    with st.spinner("Please wait..."):
                        response = st.session_state.gemini_client.generate_content(
                            f"{system_prompt}\n\nUser question: {user_message}"
                        )
                        full_response = response.text
                        message_placeholder.markdown(full_response)
                except Exception as e:
                    error_msg = "❌ Please try again."
                    message_placeholder.markdown(error_msg)
                    full_response = error_msg

            st.session_state.chat_history.append({"role": "assistant", "content": full_response})
            st.rerun()

    # ============================================================
    # --- Research Paper Explorer ---
    # ============================================================
    st.markdown("---")
    st.header("📚 Research Paper Explorer")
    st.write("Search for research papers related to your gene, CRISPR techniques, or specific topics.")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Papers about CRISPR off-targets"):
            papers = search_openalex("CRISPR off-target effects")
            if papers:
                st.subheader("Recent papers on CRISPR off-targets:")
                for paper in papers:
                    formatted = format_paper_result(paper)
                    with st.expander(f"📄 {formatted['title']} ({formatted['year']})"):
                        display_paper_details(formatted)

    with col2:
        gene_label = locus_tag
        if gene_label:
            if st.button(f"Papers about {gene_label}"):
                papers = search_openalex(gene_label)
                if papers:
                    st.subheader(f"Papers related to {gene_label}:")
                    for paper in papers:
                        formatted = format_paper_result(paper)
                        with st.expander(f"📄 {formatted['title']} ({formatted['year']})"):
                            display_paper_details(formatted)

    with col3:
        if st.button("Papers on gRNA design"):
            papers = search_openalex("guide RNA design optimization")
            if papers:
                st.subheader("Papers on gRNA design:")
                for paper in papers:
                    formatted = format_paper_result(paper)
                    with st.expander(f"📄 {formatted['title']} ({formatted['year']})"):
                        display_paper_details(formatted)

    st.markdown("### Custom Literature Search")
    custom_query = st.text_input("Enter your search query:", placeholder="e.g., CRISPR Cas9 plant genome editing")
    if st.button("🔍 Search"):
        if custom_query:
            with st.spinner("Searching database..."):
                papers = search_openalex(custom_query, per_page=10)
                if papers:
                    st.success(f"Found {len(papers)} papers")
                    for paper in papers:
                        formatted = format_paper_result(paper)
                        with st.expander(f"📄 {formatted['title']} ({formatted['year']})"):
                            display_paper_details(formatted)
                else:
                    st.info("No papers found. Try a different query.")

    # ============================================================
    # --- Critical Off-Target Genes Research ---
    # ============================================================
    st.markdown("---")
    st.header("🧬 Critical Off-Target Genes Research")
    st.write("Explore research papers for each gene identified in your critical off-target analysis.")

    all_critical_genes = []
    seen_genes = set()
    for grna in st.session_state.analysis_result:
        for critical in grna['critical_off_targets']:
            if critical['gene'] and critical['gene'] not in seen_genes:
                all_critical_genes.append(critical['gene'])
                seen_genes.add(critical['gene'])

    if all_critical_genes:
        st.info(f"Found {len(all_critical_genes)} unique critical genes across all gRNAs")
        for gene in all_critical_genes:
            with st.expander(f"🔍 Papers for gene: **{gene}**", expanded=False):
                st.write(f"Searching for papers related to {gene}...")
                papers = search_openalex(gene, per_page=5)
                if papers:
                    st.success(f"Found {len(papers)} papers for {gene}")
                    for idx, paper in enumerate(papers, 1):
                        formatted = format_paper_result(paper)
                        with st.expander(f"📄 {idx}. {formatted['title']} ({formatted['year']})"):
                            display_paper_details(formatted)
                else:
                    st.info(f"No papers found for {gene} in OpenAlex database. Try searching for related terms.")
    else:
        st.info("No critical off-target genes found in your analysis.")
