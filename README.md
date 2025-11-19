# 🧾 Document Processing Agent

This project is an end-to-end autonomous workflow system that processes invoices from multiple sources, extracts structured data using an LLM-based pipeline, validates the extracted fields, and pushes clean data to an ERP system. It operates continuously through background agents for real-time automation.

---

## Key Features

#### 1. Multi-Source Invoice Intake

 - **Email Watcher Agent**:  Automatically fetches invoice attachments from Gmail (IMAP).
 - **Folder Watcher Agent**: Monitors incoming directories for dropped files (PDFs or images).
 - **Webhook-based Upload**: Supports direct uploads from frontend or external systems.

#### 2. Intelligent OCR and Text Cleaning

- Converts PDF → Images
- Performs high-accuracy OCR
- **Cleans noisy text using:**
- 
    - Unicode sanitization
    - Non-printable character removal
    - Spacing normalization
    - UTF-8 encoding correction

#### 3. LLM-Based Field Extraction (No Regex)

- Uses Groq LLM for extraction
- Corrects OCR mistakes
- Understands fragmented or noisy invoice text
- **Extracts:**
    - Customer Name
    - Email
   -  Invoice Date
   -  Reference Number
   -  Line Items (description, quantity, rate)
      
#### 4. Data Validation Layer

  - Ensures required fields are present
  - Ensures item structure is clean
  - Prevents incomplete/malformed invoices from reaching ERP
    
#### 5. ERP Integration Layer

  - Pushes structured invoice JSON into ERP (Zoho Books or others)
  - Can easily integrate with REST APIs
  - Built-in error handling and fallback

#### 6. Autonomous Workflow Agent
**Runs:**
- Email pipeline
- Folder pipeline
- OCR → LLM extraction
- Validation
- ERP push
- Automatically, without human intervention.
---
### System Architecture
                ┌──────────────────────┐
                │ Incoming Invoices     │
                │  • Email (IMAP)       │
                │  • Folder Watcher     │
                └─────────┬────────────┘
                          │
                ┌─────────▼──────────┐
                │  Preprocessing      │
                │  • PDF → Images     │
                │  • OCR Extraction   │
                │  • Text Cleaning    │
                └─────────┬──────────┘
                          │
                ┌─────────▼──────────┐
                │  LLM Extractor      │
                │  (Groq AI)          │
                │  • Fix OCR Errors   │
                │  • Extract Fields   │
                │  • Normalize JSON   │
                └─────────┬──────────┘
                          │
                ┌─────────▼──────────┐
                │ Validation Engine   │
                │  • Required Fields  │
                │  • Valid Line Items │
                └─────────┬──────────┘
                          │
                ┌─────────▼──────────┐
                │  ERP Connector      │
                │  (Zoho Books API)   │
                └─────────────────────┘

---
### Tech Stack
- **Backend**
     - Python
     - FastAPI
     - Uvicorn
     - Tesseract OCR
     - Groq LLM (compound-mini)
    - dotenv
    - Requests
- Agents
   - Email Watcher (IMAP)
   - Folder Watcher
   - Autonomous Workflow Executor

---
### 🧩 Folder Structure
```
document_processing_agent/
│
├── backend/
│ ├── main.py # FastAPI entrypoint
│ ├── ocr_extractor.py # PDF/image OCR logic (Tesseract + Poppler + CV2)
│ ├── llm_extractor.py # LLM-powered data parsing
│ ├── data_validator.py # Field validation & cleanup
│ ├── db.py # SQLite or Postgres database operations
│ ├── erp_integration.py # Odoo or ERPNext connection logic
│ └── Agents/
|   ├──  email_watcher.py
│   ├── folder_watcher.py
│   ├── workflow_agent.py
│
├── frontend/
│ └── app.py # Streamlit UI (file upload + status display)
│
├── .env # credentials for ERP & APIs
├── requirements.txt
└── README.md
```
---
### Architecture Diagram: 
                      ┌─────────────────────────────────────┐
                      │           Input Sources              │
                      │--------------------------------------│
                      │ • Email Watcher (IMAP Agent)         │
                      │ • Folder Watcher Agent               │
                      │ • Manual Upload API (FastAPI)        │
                      └───────────────────────┬──────────────┘
                                              │  (PDF/Image)
                        ┌──────────────────────────────┐
                        │     Preprocessing Layer       │
                        │-------------------------------│
                        │ • PDF → Image Converter       │
                        │ • OCR Engine (Tesseract)      │
                        │ • Unicode Sanitizer           │
                        └───────────────┬───────────────┘
                                        │  (Clean Text)
                     ┌──────────────────▼─────────────────────┐
                     │        LLM Extraction Engine            │
                     │-----------------------------------------│
                     │ • Groq LLM (compound-mini)              │
                     │ • OCR error correction                  │
                     │ • Field extraction (JSON)               │
                     │ • Line items parsing                    │
                     └───────────────────┬─────────────────────┘
                                         │ (Structured JSON)
                 ┌───────────────────────▼────────────────────────┐
                 │               Validation Layer                  │
                 │-------------------------------------------------│
                 │ • Check required fields                         │
                 │ • Clean & normalize items                       │
                 │ • Reject malformed or incomplete invoices       │
                 └─────────────────────────┬───────────────────────┘
                                           │ (Valid JSON)
               ┌───────────────────────────▼──────────────────────────┐
               │                 ERP Integration Layer                 │
               │------------------------------------------------------│
               │ • Zoho Books API                                     │
               │ • Error handling & retry                             │
               │ • Logging pushed data                                │
               └──────────────────────────┬───────────────────────────┘
                                          │
                     ┌────────────────────▼─────────────────────┐
                     │            Storage Layer                 │
                     │-------------------------------------------│
                     │ • processed_invoices/                    │
                     │ • failed_invoices/                       │
                     │ • Logs & metrics                         │
                     └──────────────────────────────────────────┘

                         ┌─────────────────────────────────┐
                         │     Autonomous Workflow Agent    │
                         │----------------------------------│
                         │ Orchestrates the entire pipeline │
                         │ Monitors → Processes → Pushes    │
                         │ Works 24/7 autonomously           │
                         └───────────────────────────────────┘


---
### How It Works (Pipeline)

- Invoice arrives (Email, folder, or upload).
- PDF converts to images
- OCR extracts raw text.
- Text is cleaned for safe LLM parsing.
- LLM returns structured JSON.
- Data validation checks mandatory fields.
- If valid → sent to ERP.
- If invalid → stored in error folder with logs.

---
### Environment Variables 
  **Create .env:**
  ```
  GROQ_API_KEY=your_key
  EMAIL_USER=your_email
  EMAIL_PASS=your_password
  ZOHO_CLIENT_ID=your_id
  ZOHO_CLIENT_SECRET=your_secret
  ZOHO_REFRESH_TOKEN=your_refresh
  ERP_ORG_ID=your_org
  ```

---
## 🛠️ Setup Instructions

### 1️⃣ Clone the repository
```bash
git clone https://github.com/<your-username>/document-processing-agent.git
cd document-processing-agent
```
2️⃣ Create and activate a virtual environment
```
python -m venv .venv
.venv\Scripts\activate     # on Windows
source .venv/bin/activate  # on Linux/Mac
```
3️⃣ Install dependencies
```
pip install -r requirements.txt
```
4️⃣ Configure environment variables

# OCR
```
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
POPPLER_PATH=C:\poppler-25.07.0\Library\bin
```
5️⃣ Run the backend (FastAPI)
```
uvicorn backend.main:app --reload
```
Backend runs on: http://127.0.0.1:8000/docs

6️⃣ (Optional) Run the Streamlit frontend
```
streamlit run frontend/app.py
```

📸 Example Output
```
✅ Extracted text using OCR on image
🧾 Cleaned OCR Text: STRIPESSHOP INVOICE NUMBER 9000000001
🔍 Extracted fields: {'invoice_number': '9000000001', 'invoice_date': 'Dec 11, 2020', 'total': '162.37', 'vendor_name': 'StripesShop'}
✅ Invoice Processed Successfully!
```
---
**Future Enhancements**

- Automated payment reconciliation
- Vendor-wise accuracy analytics dashboard - Real-time error heatmap for OCR mistakes
- Multi-language invoice support
- AI-based fraud pattern detection
- Auto-categorization of expenses

----
<img width="2870" height="1439" alt="Screenshot 2025-11-06 124804" src="https://github.com/user-attachments/assets/ed805bd7-b11e-4208-95e7-0784f473110c" />

-----
<img width="2869" height="1449" alt="Screenshot 2025-11-06 124828" src="https://github.com/user-attachments/assets/764f4612-ded2-4e9d-894c-efa1ea5a9848" />

----
<img width="2880" height="1620" alt="Screenshot 2025-11-06 124726" src="https://github.com/user-attachments/assets/481f59c2-9920-4f43-bbcb-97b05d3dec23" />
----
<img width="789" height="672" alt="Screenshot 2025-11-06 151108" src="https://github.com/user-attachments/assets/a40f4193-d503-4fea-a43e-b60d6ad689d0" />

----
<img width="2869" height="1461" alt="Screenshot 2025-11-06 182336" src="https://github.com/user-attachments/assets/691cb474-5f11-45f9-8b69-834de7e4e66c" />
---
<img width="2880" height="1620" alt="Screenshot 2025-11-06 182411" src="https://github.com/user-attachments/assets/a040d812-aad8-4102-8591-ee434645f1ed" />

---

