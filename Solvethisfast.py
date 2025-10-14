import streamlit as st
import pandas as pd
from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import time
import tempfile

# --- Page Configuration ---
st.set_page_config(
    page_title="CRISPR gRNA Analysis Tool",
    page_icon="🔬",
    layout="wide"
)

# --- Selenium WebDriver Setup ---
# def get_driver():
#     """Creates a fresh Selenium WebDriver instance with extended timeouts."""
#     try:
#         options = Options()
#         options.add_argument("--headless=new")
#         options.add_argument("--disable-gpu")
#         options.add_argument("--remote-allow-origins=*")
#         options.add_argument("--disable-dev-shm-usage")
#         options.add_argument("--no-sandbox")
#         options.add_argument("--disable-blink-features=AutomationControlled")
#         options.add_experimental_option("detach", True)
        
#         user_data_dir = tempfile.mkdtemp()
#         options.add_argument(f"--user-data-dir={user_data_dir}")
        
#         service = Service(ChromeDriverManager().install())
#         driver = webdriver.Chrome(service=service, options=options)
        
#         driver.set_page_load_timeout(600)
#         driver.set_script_timeout(600)
#         driver.command_executor.set_timeout(600)
        
#         return driver
#     except Exception as e:
#         st.error(f"Failed to initialize Chrome driver: {e}")
#         return None
def get_driver():
    """Creates a fresh Selenium WebDriver instance with extended timeouts."""
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--remote-allow-origins=*")
        
        # For Streamlit Cloud, directly use Chrome without ChromeDriverManager
        driver = webdriver.Chrome(options=options)
                # Set extended timeouts for slow CRISPR website
        driver.set_page_load_timeout(600)
        driver.set_script_timeout(600)
        driver.command_executor.set_timeout(600)  
        
        driver.set_page_load_timeout(600)
        driver.set_script_timeout(600)
        
        return driver
    except Exception as e:
        st.error(f"Failed to initialize Chrome driver: {e}")
        return None


# --- Helper Functions ---
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
    """
    Find the correct results table by looking for the table with gRNA data.
    The results table should have rows with sequences and scores.
    """
    try:
        # Wait for any table to load first
        wait = WebDriverWait(driver, 180)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        
        # Get all tables on the page
        all_tables = driver.find_elements(By.TAG_NAME, "table")
        
        if 'status' in st.session_state:
            st.session_state.status.update(label=f"Found {len(all_tables)} table(s) on page. Searching for results table...")
        
        # Strategy 1: Look for table with class or id containing specific keywords
        for table in all_tables:
            try:
                table_html = table.get_attribute("outerHTML").lower()
                # Check if this looks like a results table
                if any(keyword in table_html for keyword in ['guide', 'score', 'sequence', 'region']):
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    if len(rows) >= 2:  # At least header + 1 data row
                        # Check if first row has column headers we expect
                        first_row = rows[0]
                        first_row_text = first_row.text.lower()
                        if any(col in first_row_text for col in ['score', 'sequence', 'region', 'gc']):
                            if 'status' in st.session_state:
                                st.session_state.status.update(label=f"Found results table with {len(rows)} rows.")
                            return table
            except:
                continue
        
        # Strategy 2: Look for the table with the most rows (likely the results table)
        max_rows = 0
        results_table = None
        for table in all_tables:
            try:
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) > max_rows and len(rows) >= 3:  # At least 3 rows (header + 2 data)
                    # Verify it has td elements (data cells)
                    if rows[1].find_elements(By.TAG_NAME, "td"):
                        max_rows = len(rows)
                        results_table = table
            except:
                continue
        
        if results_table:
            if 'status' in st.session_state:
                st.session_state.status.update(label=f"Selected table with {max_rows} rows as results table.")
            return results_table
        
        # Strategy 3: Fallback to first table with data rows
        for table in all_tables:
            try:
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) >= 2:
                    # Check if it has actual data (not just navigation)
                    first_data_row = rows[1] if len(rows) > 1 else rows[0]
                    cells = first_data_row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 3:  # At least 3 columns
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
        
        sequence_col = -1
        region_col = -1
        gene_col = -1
        score_col = -1
        
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

def analyze_crispr_results(driver):
    """The main analysis function to parse, prioritize, and re-rank gRNAs."""
    try:
        # Find the correct results table
        main_table = find_results_table(driver)
        
        rows = main_table.find_elements(By.TAG_NAME, "tr")
        
        if len(rows) < 2:
            raise ValueError("No gRNA results found in the table. The locus tag may not exist or produced no results.")
        
        if 'status' in st.session_state:
            st.session_state.status.update(label=f"Parsing {len(rows)-1} gRNA results from table...")
        
        grna_data = []
        
        # Extract gRNA data from main table
        for i, row in enumerate(rows[1:], 1):  # Skip header row
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 3:
                cell_texts = [cell.text.strip() for cell in cells]
                
                grna_element = None
                grna_sequence = ""
                score = 0.0
                gc_content = 0.0
                region = ""
                
                # Look for gRNA sequence in cells (typically 20-23 nucleotides ending with GG)
                for j, cell in enumerate(cells):
                    text = cell.text.strip()
                    # gRNA sequences are typically 20-23bp long and contain only ATCG
                    if len(text) >= 20 and len(text) <= 25 and all(c.upper() in 'ATCG' for c in text if c.isalpha()):
                        grna_sequence = text
                        grna_element = cell
                        break
                
                # Extract score (decimal between 0 and 1)
                for text in cell_texts:
                    try:
                        val = float(text)
                        if 0.0 <= val <= 1.0 and '.' in text:
                            score = val
                            break
                    except ValueError:
                        pass
                
                # Extract GC content (percentage)
                for text in cell_texts:
                    if '%' in text:
                        try:
                            gc_content = float(text.replace('%', ''))
                            break
                        except ValueError:
                            pass
                
                # Extract region (exon, intron, utr, cds)
                for text in cell_texts:
                    text_lower = text.lower()
                    if text_lower in ['exon', 'utr', 'intron', 'cds', '5\'utr', '3\'utr']:
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
        
        # Prioritization Logic
        high_score = [g for g in grna_data if g['score'] > 0.0000]
        good_gc = [g for g in high_score if g['gc_content'] > 40.0]
        
        region_priority = {'exon': 3, 'utr': 2, 'intron': 1, 'cds': 2, '5\'utr': 2, '3\'utr': 2}
        
        prioritized_grnas = sorted(
            good_gc,
            key=lambda x: (region_priority.get(x['region'], 0), x['score']),
            reverse=True
        )
        
        top_grnas = prioritized_grnas[:20] if len(prioritized_grnas) >= 20 else prioritized_grnas
        
        if len(top_grnas) == 0:
            raise ValueError("No gRNAs passed quality filters (score > 0.0, GC content > 40%). Try different parameters or locus tag.")
        
        if 'status' in st.session_state:
            st.session_state.status.update(label=f"Found {len(top_grnas)} high-quality gRNAs. Analyzing off-targets...")
        
        # Get off-target data for each gRNA
        for idx, grna in enumerate(top_grnas):
            off_targets = get_off_target_data_by_interaction(driver, grna['element'])
            grna['off_targets'] = off_targets
            grna['off_target_count'] = len(off_targets)
            
            critical_off_targets = []
            for off_target in off_targets:
                if off_target['region'] in ['exon', 'cds', 'utr']:
                    critical_off_targets.append(off_target)
            
            grna['critical_off_targets'] = critical_off_targets
            grna['critical_count'] = len(critical_off_targets)
            
            if 'status' in st.session_state:
                st.session_state.status.update(label=f"Analyzing off-targets for gRNA {idx + 1}/{len(top_grnas)}...")
            time.sleep(1)
        
        # Final Re-prioritization
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

# --- Streamlit App UI ---
st.title("🔬 CRISPR gRNA Design & Analysis")
st.write("This tool automates gRNA design using the CRISPR-PLANT website, then performs a comprehensive off-target analysis to identify the safest and most effective candidates.")

# Initialize session state variables
if 'genomes_list' not in st.session_state:
    st.session_state.genomes_list = None
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None

# --- Sidebar for User Inputs ---
with st.sidebar:
    st.header("1. Input Parameters")
    locus_tag = st.text_input("Locus Tag", "GLYMA14G07880", help="Enter the gene identifier (e.g., AT2G43010).")
    snoRNA = st.checkbox("Check snoRNA?", True)
    
    st.header("2. Genome Selection")
    
    if st.button("Fetch Available Genomes"):
        with st.spinner("Connecting to CRISPR-PLANT to get genome list..."):
            driver = get_driver()
            if driver:
                try:
                    driver.get("http://crispr.hzau.edu.cn/cgi-bin/CRISPR2/CRISPR")
                    time.sleep(5)
                    
                    wait = WebDriverWait(driver, 30)
                    start_link = wait.until(
                        EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Start"))
                    )
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
            "Select Genome",
            st.session_state.genomes_list,
            index=default_index,
            help="Select the target genome from the list fetched from the website."
        )
        st.success(f"{len(st.session_state.genomes_list)} genomes loaded successfully!")
    else:
        st.info("Click 'Fetch Available Genomes' to load the list from the CRISPR-PLANT website.")
    
    st.header("3. Run Analysis")
    run_button = st.button("🚀 Design and Analyze gRNAs", type="primary", disabled=(not st.session_state.genomes_list))

# --- Main Page for Outputs ---
if run_button:
    st.session_state.analysis_result = None
    driver = get_driver()
    
    if not driver:
        st.error("Failed to initialize web driver. Please try again.")
    else:
        with st.status("Running CRISPR Analysis Pipeline...", expanded=True) as status:
            st.session_state.status = status
            
            try:
                # Step 1: Navigate and submit form
                status.update(label="Navigating to CRISPR-PLANT and submitting your job...")
                driver.get("http://crispr.hzau.edu.cn/cgi-bin/CRISPR2/CRISPR")
                time.sleep(5)
                
                wait = WebDriverWait(driver, 30)
                start_link = wait.until(
                    EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Start"))
                )
                start_link.click()
                time.sleep(3)
                
                dropdown = wait.until(EC.presence_of_element_located((By.ID, "name_db")))
                dropdown.find_element(By.XPATH, f"//option[. = '{selected_genome}']").click()
                time.sleep(1)
                
                locus_input = wait.until(EC.presence_of_element_located((By.ID, "loc_search")))
                locus_input.clear()
                locus_input.send_keys(locus_tag)
                
                if snoRNA:
                    driver.find_element(By.CSS_SELECTOR, "label:nth-child(2) > #ppp").click()
                
                submit_button = wait.until(
                    EC.element_to_be_clickable((By.NAME, ".submit"))
                )
                submit_button.click()
                
                status.update(label=f"Job submitted for '{locus_tag}'. Waiting for results... (This can take up to a minute)")
                time.sleep(20)
                
                # Step 2: Analyze the results
                status.update(label="Results received! Parsing and analyzing gRNAs...")
                final_results = analyze_crispr_results(driver)
                st.session_state.analysis_result = final_results
                status.update(label="Analysis Complete!", state="complete", expanded=False)
                
            except TimeoutException as e:
                status.update(label="Timeout error occurred!", state="error")
                st.error(f"⏱️ **Timeout Error**: {str(e)}")
                st.warning(f"**Possible reasons:**\n- The locus tag '{locus_tag}' may not exist in the selected genome\n- The CRISPR server is taking too long to respond\n- Network connectivity issues\n\n**Suggestions:**\n- Verify the locus tag is correct for '{selected_genome}'\n- Try again in a few minutes\n- Try a different locus tag that is known to work")
                
            except NoSuchElementException as e:
                status.update(label="Could not find results!", state="error")
                st.error(f"❌ **Element Not Found**: {str(e)}")
                st.warning(f"**Possible reasons:**\n- The locus tag '{locus_tag}' does not exist in '{selected_genome}'\n- The results page structure is different than expected\n- No gRNAs could be designed for this target\n\n**Suggestions:**\n- Double-check the locus tag spelling and format\n- Verify this gene exists in the selected genome\n- Try a different locus tag (e.g., 'GLYMA14G07880' or 'GLYMA13G08120' work for Glycine max)")
                
            except ValueError as e:
                status.update(label="No results found!", state="error")
                st.error(f"❌ **No Valid Results**: {str(e)}")
                st.warning(f"The analysis completed but no valid gRNAs were found that meet the quality criteria.")
                
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

# Display the results if they exist in the session state
if st.session_state.analysis_result:
    st.header("📊 Analysis Results")
    
    results_data = []
    for grna in st.session_state.analysis_result:
        critical_genes = []
        for critical in grna['critical_off_targets']:
            if critical['gene'] and critical['gene'] not in critical_genes:
                critical_genes.append(critical['gene'])
                
        critical_genes_str = ', '.join(critical_genes)
        # critical_genes_str = ', '.join(critical_genes[:3])
        # if len(critical_genes) > 3:
        #     critical_genes_str += f" (+{len(critical_genes)-3} more)"
        
        results_data.append({
            'sequence': grna['sequence'],
            'score': grna['score'],
            'gc_content': grna['gc_content'],
            'region': grna['region'],
            'off_target_count': grna['off_target_count'],
            'critical_count': grna['critical_count'],
            'critical_genes': critical_genes_str
        })
    
    results_df = pd.DataFrame(results_data)
    results_df.insert(0, 'Rank', range(1, len(results_df) + 1))
    
    st.write(f"Found and prioritized **{len(results_df)}** gRNAs")
    
    st.dataframe(results_df[['Rank', 'sequence', 'gc_content', 'region', 'critical_count', 'off_target_count', 'critical_genes']], use_container_width=True)
    
    # # Display detailed analysis of the best gRNA
    # best_grna = st.session_state.analysis_result[0]
    # st.header("🥇 Top Ranked gRNA Candidate")
    
    # col1, col2, col3, col4 = st.columns(4)
    # col1.metric("On-Target Score", f"{best_grna['score']:.4f}")
    # col2.metric("GC Content", f"{best_grna['gc_content']:.1f}%")
    # col3.metric("Critical Off-Targets", best_grna['critical_count'])
    # col4.metric("Total Off-Targets", best_grna['off_target_count'])
    
    # st.write(f"**Sequence**: `{best_grna['sequence']}`")
    # st.write(f"**Target Region**: `{best_grna['region']}`")
    
    # with st.expander("View Critical Off-Target Details"):
    #     if best_grna['critical_off_targets']:
    #         off_target_df = pd.DataFrame(best_grna['critical_off_targets'])
    #         st.dataframe(off_target_df, use_container_width=True)
            
    #         critical_genes = [ot['gene'] for ot in best_grna['critical_off_targets'] if ot['gene']]
    #         unique_critical_genes = list(set(critical_genes))
            
    #         if unique_critical_genes:
    #             st.subheader("Critical Gene IDs:")
    #             for gene in unique_critical_genes:
    #                 st.write(f"• **{gene}**")
    #     else:
    #         st.success("✅ No critical off-targets found for the top-ranked gRNA!")




