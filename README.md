# 🚀 JobAI - AI-Powered ATS Resume Tailoring Platform

JobAI is an intelligent, full-stack application designed to analyze, score, and tailor resumes specifically for Job Descriptions (JDs) to maximize ATS (Applicant Tracking System) match rates.

It combines a **FastAPI** backend with **LangChain & Groq AI**, **ChromaDB** vector search, **Tectonic LaTeX compilation**, and a modern **Next.js 16** frontend built with React & JavaScript.

---

## 🌟 Key Features

* **⚡ ATS Match Scoring Engine**:
  * Calculates exact **Keyword Coverage %** and **Semantic Similarity %**.
  * Detects missing hard skills and experience gaps.
  * Displays scorer warnings, penalties, and real-time score deltas (Before vs. After tailoring).

* **🎯 Interactive Bullet-by-Bullet Rewriting**:
  * Click on any bullet point in your experience or projects section to get an AI-tailored bullet point aligned with the target Job Description.
  * Review side-by-side diffs with AI reasoning, then **Accept** or **Reject** suggestions in 1 click.

* **✨ Targeted Section Optimization**:
  * **Summary Alignment**: AI rewrites your executive summary to target key requirements without fabricating details.
  * **Technical Skills Tailoring**: Automatically categorizes and optimizes skills while verifying constraints against hallucination.

* **📄 PDF Generation & LaTeX Compilation**:
  * Compiles tailored resume data directly into a clean, professional LaTeX template using **Tectonic**.
  * Preview & download export-ready PDF resumes directly from the web interface.

* **📊 Tracker Dashboard**:
  * Track all your job applications, role titles, target companies, and current ATS match scores in one centralized dashboard.

---

## 🛠️ Tech Stack

### **Frontend**
* **Framework:** Next.js 16 (App Router, React 19)
* **Language:** JavaScript (`.jsx` / `.js`)
* **Styling:** Vanilla CSS design system with responsive glassmorphism aesthetic

### **Backend**
* **Framework:** FastAPI (Python 3.10+)
* **Server:** Uvicorn
* **AI Orchestration:** LangChain + Groq API (`llama-3.3-70b-versatile` / `mixtral`)
* **Vector Database:** ChromaDB (for semantic embeddings & similarity search)
* **Parsers & Utilities:** `pdfplumber`, `python-docx`, `rapidfuzz`
* **LaTeX Engine:** Tectonic (embedded PDF compiler)

### **Database & Infrastructure**
* **Database:** MariaDB / MySQL (SQLAlchemy ORM + PyMySQL)
* **Containers:** Docker & Docker Compose

---

## 📁 Repository Structure

```
JobAI/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point & API endpoints
│   │   ├── ai.py                # LangChain & Groq AI tailoring logic
│   │   ├── scorer.py            # ATS scoring, keyword & semantic engine
│   │   ├── matching.py          # Vector search & embeddings logic
│   │   ├── database.py          # Database session configuration
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── parsers.py           # PDF/DOCX text extraction
│   │   ├── pdf_compiler.py      # Tectonic LaTeX PDF compiler
│   │   └── latex_template.py    # Dynamic LaTeX template engine
│   ├── requirements.txt         # Python dependencies
│   └── tests/                   # Test suite
│
├── frontend/
│   ├── src/
│   │   └── app/
│   │       ├── page.jsx                      # Applications Dashboard
│   │       ├── upload/page.jsx               # New Application form
│   │       └── applications/[id]/page.jsx    # Interactive Tailoring Studio
│   ├── next.config.mjs
│   └── package.json
│
├── docker-compose.yml           # Database service container setup
└── README.md                    # Project documentation
```

---

## 🚦 Getting Started

### Prerequisites
* **Python** 3.10+
* **Node.js** 18+ & `npm`
* **Docker Desktop** (optional, for MariaDB)
* **Groq API Key** (for AI tailoring features)

---

### 1️⃣ Setting up the Backend

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Mac/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure Environment Variables:
   Create a `.env` file in the `backend/` directory:
   ```env
   DATABASE_URL=sqlite:///./jobai.db
   GROQ_API_KEY=your_groq_api_key_here
   ```

5. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   The backend API will be available at `http://127.0.0.1:8000`. API docs are at `http://127.0.0.1:8000/docs`.

---

### 2️⃣ Setting up the Frontend

1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```

2. Install Node dependencies:
   ```bash
   npm install
   ```

3. Start the Next.js development server:
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to `http://localhost:3000`.

---

## 🔄 Workflow / How It Works

1. **Upload Resume & JD**: Upload your original resume (`.pdf` or `.docx`) and paste the job description you are targeting.
2. **Initial Scoring**: The backend parses the resume into structured JSON, extracts keywords, calculates vector semantic similarity, and generates an initial ATS match score.
3. **Interactive Tailoring**:
   * Click any bullet point to get instant, AI-generated rewrites optimized for the target job.
   * Tailor your Executive Summary or Technical Skills section with 1-click AI optimization.
   * View live ATS score updates as you accept suggestions.
4. **Export PDF**: Click **Preview PDF** or **Download PDF** to export your tailored resume compiled directly via LaTeX.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
