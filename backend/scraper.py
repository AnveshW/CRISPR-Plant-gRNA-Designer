import os
import time
import logging
import tempfile
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

logger = logging.getLogger("crispr_scraper")

class CRISPRScraper:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback or (lambda x: None)

    def log(self, message: str, level=logging.INFO):
        logger.log(level, message)
        self.progress_callback(message)

    def _get_driver(self):
        """Creates a fresh, optimized Selenium headless Chrome driver."""
        self.log("Initializing headless Chrome browser...")
        try:
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--remote-allow-origins=*")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-blink-features=AutomationControlled")

            chrome_bin = os.getenv("CHROME_BIN")
            if chrome_bin:
                options.binary_location = chrome_bin
                self.log(f"Using Chrome binary at: {chrome_bin}")

            user_data_dir = tempfile.mkdtemp()
            options.add_argument(f"--user-data-dir={user_data_dir}")

            # Explicitly use ChromeDriver path from environment if set
            chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
            if chromedriver_path:
                self.log(f"Using ChromeDriver at: {chromedriver_path}")
                service = Service(executable_path=chromedriver_path)
                driver = webdriver.Chrome(service=service, options=options)
            else:
                driver = webdriver.Chrome(options=options)

            driver.set_page_load_timeout(300)
            driver.set_script_timeout(300)
            return driver
        except Exception as e:
            self.log(f"Failed to initialize Chrome driver: {e}", logging.ERROR)
            raise e

    def fetch_genomes(self):
        """Fetches the list of available genomes from the CRISPR-PLANT server dropdown."""
        driver = None
        try:
            driver = self._get_driver()
            self.log("Connecting to CRISPR-PLANT website (http://crispr.hzau.edu.cn)...")
            driver.get("http://crispr.hzau.edu.cn/cgi-bin/CRISPR2/CRISPR")
            
            wait = WebDriverWait(driver, 30)
            self.log("Navigating to Start portal...")
            start_link = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Start")))
            start_link.click()
            time.sleep(2)
            
            self.log("Loading genome dropdown...")
            dropdown = wait.until(EC.presence_of_element_located((By.ID, "name_db")))
            options = dropdown.find_elements(By.TAG_NAME, "option")
            genomes = [opt.text.strip() for opt in options if opt.text.strip()]
            self.log(f"Successfully loaded {len(genomes)} plant genomes!")
            return genomes
        except Exception as e:
            self.log(f"Error fetching genome list: {e}", logging.ERROR)
            fallback_genomes = [
                "Glycine max (V1.0)",
                "Arabidopsis thaliana (TAIR10)",
                "Oryza sativa (IRGSP-1.0)",
                "Zea mays (AGPv3)",
                "Solanum lycopersicum (SL2.40)",
                "Medicago truncatula (Mt4.0)",
                "Populus trichocarpa (v3.0)",
                "Brachypodium distachyon (v1.0)",
                "Sorghum bicolor (v2.1)"
            ]
            self.log("Falling back to pre-defined genome list.", logging.WARNING)
            return fallback_genomes
        finally:
            if driver:
                driver.quit()

    def _submit_crispr_plant_job(self, driver, selected_genome, locus_tag, sequence, position, pam, guide_length, promoter):
        """Fills and submits the design form on the CRISPR-PLANT website."""
        self.log("Navigating to CRISPR-PLANT design portal...")
        driver.get("http://crispr.hzau.edu.cn/cgi-bin/CRISPR2/CRISPR")
        time.sleep(3)

        wait = WebDriverWait(driver, 30)
        start_link = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Start")))
        start_link.click()
        time.sleep(2)

        self.log(f"Selecting target genome: '{selected_genome}'")
        dropdown = wait.until(EC.presence_of_element_located((By.ID, "name_db")))
        try:
            dropdown.find_element(By.XPATH, f"//option[. = '{selected_genome}']").click()
        except Exception:
            self.log(f"Genome selection failed, trying fallback element match...")
            options = dropdown.find_elements(By.TAG_NAME, "option")
            matched = False
            for opt in options:
                if selected_genome.lower() in opt.text.lower() or opt.text.lower() in selected_genome.lower():
                    opt.click()
                    matched = True
                    break
            if not matched:
                raise ValueError(f"Genome '{selected_genome}' not found in the dropdown menu.")
        time.sleep(1)

        pam_options = [
            "NGG (SpCas9)", "NAG (SpCas9)", "NGA (SpCas9)",
            "NNGRRT (SaCas9)", "NNNRRT (SaCas9-KKH)",
            "TTTN (Cpf1)", "TTN (Cas12a)", "NG (SpCas9-NG)",
            "NGA (SpCas9-VQR)", "NGCG (SpCas9-VRER)",
            "TTTN (AsCpf1)", "TTTN (LbCpf1)"
        ]
        pam_index = 0
        for idx, opt in enumerate(pam_options):
            if pam in opt or opt in pam:
                pam_index = idx
                break
        
        self.log(f"Selecting PAM sequence constraint: '{pam}'")
        pam_dropdown = wait.until(EC.presence_of_element_located((By.ID, "pppp")))
        Select(pam_dropdown).select_by_index(pam_index)
        time.sleep(0.5)

        guide_length_numeric = guide_length.replace(" bp", "").strip()
        self.log(f"Setting spacer length: {guide_length_numeric} bp")
        guide_length_dropdown = wait.until(EC.presence_of_element_located((By.ID, "spacer_length")))
        try:
            Select(guide_length_dropdown).select_by_value(guide_length_numeric)
        except Exception:
            guide_length_index = int(guide_length_numeric) - 15
            Select(guide_length_dropdown).select_by_index(guide_length_index)
        time.sleep(0.5)

        self.log(f"Setting plant promoter: {promoter}")
        if "U6" in promoter:
            driver.find_element(By.CSS_SELECTOR, "label:nth-child(1) > #ppp").click()
        else:
            driver.find_element(By.CSS_SELECTOR, "label:nth-child(2) > #ppp").click()
        time.sleep(0.5)

        if locus_tag:
            self.log(f"Injecting Locus Tag target: '{locus_tag}'")
            locus_input = wait.until(EC.presence_of_element_located((By.ID, "loc_search")))
            locus_input.clear()
            locus_input.send_keys(locus_tag)
        elif sequence:
            self.log(f"Injecting target DNA sequence ({len(sequence)} bp)...")
            sequence_input = wait.until(EC.presence_of_element_located((By.ID, "sequenceid")))
            sequence_input.clear()
            sequence_input.send_keys(sequence)
        elif position:
            self.log(f"Injecting Genomic Position: '{position}'")
            position_input = wait.until(EC.presence_of_element_located((By.ID, "position")))
            position_input.clear()
            position_input.send_keys(position)

        self.log("Submitting guide RNA design request to CRISPR-PLANT engine...")
        submit_button = wait.until(EC.element_to_be_clickable((By.NAME, ".submit")))
        submit_button.click()
        self.log("Job submitted successfully! Waiting for server to process results (this takes 15-40 seconds)...")
        time.sleep(15)

    def _find_results_table(self, driver):
        """Locates the parsed results grid on the results page."""
        wait = WebDriverWait(driver, 120)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        all_tables = driver.find_elements(By.TAG_NAME, "table")

        self.log(f"Found {len(all_tables)} raw tables. Dissecting for candidate guide RNAs...")
        for table in all_tables:
            try:
                table_html = table.get_attribute("outerHTML").lower()
                if any(keyword in table_html for keyword in ['guide', 'score', 'sequence', 'region']):
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    if len(rows) >= 2:
                        first_row_text = rows[0].text.lower()
                        if any(col in first_row_text for col in ['score', 'sequence', 'region', 'gc']):
                            return table
            except Exception:
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
            except Exception:
                continue
        if results_table:
            return results_table

        for table in all_tables:
            try:
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) >= 2:
                    cells = rows[1].find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 3:
                        return table
            except Exception:
                continue

        raise NoSuchElementException("CRISPR-PLANT could not resolve the target locus tag or sequence.")

    def _get_off_target_data_by_interaction(self, driver, grna_element):
        """Scrapes off-target statistics by interacting with table elements."""
        try:
            actions = ActionChains(driver)
            actions.move_to_element(grna_element).perform()
            time.sleep(1.5)
            try:
                grna_element.click()
                time.sleep(1.5)
            except Exception:
                pass

            off_target_tables = driver.find_elements(By.XPATH, "//table[contains(@class, 'offTarget') or contains(@id, 'offTarget')]")
            if not off_target_tables:
                all_tables = driver.find_elements(By.TAG_NAME, "table")
                for table in all_tables:
                    text_lower = table.text.lower()
                    if 'off' in text_lower or 'target' in text_lower or 'gene' in text_lower:
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
            for i, h in enumerate(headers):
                if 'sequence' in h or 'seq' in h:
                    sequence_col = i
                elif 'region' in h:
                    region_col = i
                elif 'gene' in h:
                    gene_col = i
                elif 'score' in h or 'off' in h:
                    score_col = i

            for row in rows[1:]:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) > 0:
                    seq = cells[sequence_col].text.strip() if sequence_col >= 0 and sequence_col < len(cells) else ""
                    reg = cells[region_col].text.strip() if region_col >= 0 and region_col < len(cells) else ""
                    gene = cells[gene_col].text.strip() if gene_col >= 0 and gene_col < len(cells) else ""
                    score = cells[score_col].text.strip() if score_col >= 0 and score_col < len(cells) else ""

                    if not seq:
                        for cell in cells:
                            txt = cell.text.strip()
                            if len(txt) >= 15 and all(c.upper() in 'ATCG-' for c in txt if c.isalpha()):
                                seq = txt
                                break

                    if seq:
                        off_target_data.append({
                            'sequence': seq,
                            'region': reg.lower(),
                            'gene': gene,
                            'score': score
                        })
            return off_target_data
        except Exception:
            return []

    def _analyze_crispr_results(self, driver):
        """Parses, filters, and runs off-target audits on candidate guide RNAs."""
        main_table = self._find_results_table(driver)
        rows = main_table.find_elements(By.TAG_NAME, "tr")

        if len(rows) < 2:
            raise ValueError("Zero gRNA design results found on the CRISPR-PLANT web database.")

        self.log(f"Discovered {len(rows)-1} candidate gRNAs. Parsing details and metrics...")
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

                for cell in cells:
                    text = cell.text.strip()
                    if len(text) >= 15 and len(text) <= 28 and all(c.upper() in 'ATCGN' for c in text if c.isalpha()):
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

                position_val = ""
                strand_val = "+"
                for text in cell_texts:
                    if ':' in text and '/' not in text:
                        position_val = text
                        parts = text.split(':')
                        if len(parts) >= 2:
                            after_colon = parts[1]
                            if after_colon.startswith('-'):
                                strand_val = "-"
                            elif after_colon.startswith('+'):
                                strand_val = "+"
                        break

                if grna_sequence and grna_element:
                    grna_data.append({
                        'index': i,
                        'sequence': grna_sequence,
                        'score': score,
                        'gc_content': gc_content,
                        'region': region,
                        'element': grna_element,
                        'position': position_val,
                        'strand': strand_val
                    })

        if not grna_data:
            raise ValueError("No valid guide sequences could be parsed from the table.")

        self.log(f"Extracted {len(grna_data)} gRNA targets. Prioritizing candidates based on criteria...")
        
        high_score = [g for g in grna_data if g['score'] > 0.0]
        good_gc = [g for g in high_score if g['gc_content'] > 40.0]

        region_priority = {'exon': 3, 'cds': 2.5, 'utr': 2, "5'utr": 2, "3'utr": 2, 'intron': 1}
        
        prioritized_grnas = sorted(
            good_gc,
            key=lambda x: (region_priority.get(x['region'], 0), x['score']),
            reverse=True
        )

        top_grnas = prioritized_grnas[:30] if len(prioritized_grnas) >= 30 else prioritized_grnas
        
        if not top_grnas:
            self.log("No gRNAs met premium filters (Score > 0, GC > 40%). Performing fallback on all candidates.", logging.WARNING)
            top_grnas = sorted(
                grna_data,
                key=lambda x: (region_priority.get(x['region'], 0), x['score']),
                reverse=True
            )[:30]

        self.log(f"Re-ranked {len(top_grnas)} prime candidates. Performing off-target audits...")
        for idx, grna in enumerate(top_grnas):
            self.log(f"Auditing off-targets for candidate gRNA {idx+1}/{len(top_grnas)}: {grna['sequence']}")
            off_targets = self._get_off_target_data_by_interaction(driver, grna['element'])
            
            grna['off_targets'] = off_targets
            grna['off_target_count'] = len(off_targets)
            critical_off_targets = [ot for ot in off_targets if ot['region'] in ['exon', 'cds', 'utr', "5'utr", "3'utr"]]
            grna['critical_off_targets'] = critical_off_targets
            grna['critical_count'] = len(critical_off_targets)
            time.sleep(0.5)

        final_prioritized = sorted(
            top_grnas,
            key=lambda x: (
                x['critical_count'],
                x['off_target_count'],
                -region_priority.get(x['region'], 0),
                -x['score']
            )
        )

        clean_results = []
        for g in final_prioritized:
            clean_results.append({
                'sequence': g['sequence'],
                'score': g['score'],
                'gc_content': g['gc_content'],
                'region': g['region'],
                'off_target_count': g['off_target_count'],
                'critical_count': g['critical_count'],
                'off_targets': g['off_targets'],
                'position': g.get('position', ''),
                'strand': g.get('strand', '+')
            })
        return clean_results

    def run_design_pipeline(self, selected_genome, locus_tag=None, sequence=None, position=None, pam="NGG (SpCas9)", guide_length="20 bp", promoter="U3", max_retries=2):
        """Runs the design pipeline with automatic retries for server reliability."""
        last_error = None
        for attempt in range(1, max_retries + 1):
            self.log(f"=== Execution Attempt {attempt}/{max_retries} ===")
            driver = None
            try:
                driver = self._get_driver()
                self._submit_crispr_plant_job(
                    driver=driver, selected_genome=selected_genome,
                    locus_tag=locus_tag, sequence=sequence, position=position,
                    pam=pam, guide_length=guide_length, promoter=promoter
                )
                results = self._analyze_crispr_results(driver)
                self.log(f"Design completed with {len(results)} optimal guide RNAs identified!")
                return results
            except Exception as e:
                last_error = e
                self.log(f"Attempt {attempt} failed: {type(e).__name__}: {str(e)}", logging.WARNING)
                if attempt < max_retries:
                    self.log(f"Cooling down 5s before next attempt...", logging.WARNING)
                    time.sleep(5)
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
        
        self.log(f"All {max_retries} pipeline attempts failed.", logging.ERROR)
        raise last_error
