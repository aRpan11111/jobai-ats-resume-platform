import json

def json_to_latex(parsed_json) -> str:
    if isinstance(parsed_json, str):
        try:
            parsed_json = json.loads(parsed_json)
        except:
            parsed_json = {}
    if not isinstance(parsed_json, dict):
        parsed_json = {}
        
    # Escape LaTeX special characters
    def escape(text):
        if not text:
            return ""
        text = str(text).replace('\n', ' ').replace('\r', '')
        chars = {
            '\\': r'\textbackslash{}',
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '^': r'\textasciicircum{}',
        }
        for k, v in chars.items():
            text = text.replace(k, v)
        return text

    # Extract contact info
    contact_info = parsed_json.get("contact_info", {})
    name = escape(contact_info.get("name", "Candidate Name"))
    email = escape(contact_info.get("email", "email@example.com"))
    phone = escape(contact_info.get("phone", "555-0100"))
    linkedin_raw = contact_info.get("linkedin", "linkedin.com/in/username")
    linkedin = linkedin_raw if linkedin_raw.startswith("http") else f"https://{linkedin_raw}"
    linkedin_display = escape(linkedin_raw.replace("https://", "").replace("http://", ""))
    github_raw = contact_info.get("github", "")
    github = github_raw if not github_raw or github_raw.startswith("http") else f"https://{github_raw}"
    github_display = escape(github_raw.replace("https://", "").replace("http://", ""))

    latex = r"""\documentclass[letterpaper,11pt]{article}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage{fontawesome5}

\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\addtolength{\oddsidemargin}{-0.6in}
\addtolength{\textwidth}{1.2in}
\addtolength{\topmargin}{-0.7in}
\addtolength{\textheight}{1.9in}

\titleformat{\section}{\vspace{-3pt}\scshape\raggedright\large\bfseries}{}{0em}{}[\titlerule \vspace{-5pt}]

\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}
\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

\begin{document}
"""
    # Header
    latex += r"\begin{center}" + "\n"
    latex += rf"    {{\Huge \scshape {name}}} \\ \vspace{{1pt}}" + "\n"
    latex += rf"    {phone} $|$ \href{{mailto:{email}}}{{\underline{{{email}}}}} $|$ " + "\n"
    latex += rf"    \href{{{linkedin}}}{{\underline{{{linkedin_display}}}}}"
    if github:
        latex += rf" $|$ \href{{{github}}}{{\underline{{{github_display}}}}}"
    latex += "\n"
    latex += r"\end{center}" + "\n\n"

    # Summary
    if "summary" in parsed_json and parsed_json["summary"]:
        latex += r"\section{Summary}" + "\n"
        latex += r"\small{" + escape(parsed_json["summary"]) + r"}" + "\n\n"

    # Education
    if "education" in parsed_json and parsed_json["education"]:
        latex += r"\section{Education}" + "\n"
        latex += r"\resumeSubHeadingListStart" + "\n"
        for edu in parsed_json["education"]:
            latex += r"  \resumeSubheading" + "\n"
            latex += f"    {{{escape(edu.get('institution', ''))}}}{{{escape(edu.get('dates', ''))}}}\n"
            latex += f"    {{{escape(edu.get('degree', ''))}}}{{}}\n"
        latex += r"\resumeSubHeadingListEnd" + "\n\n"

    # Experience
    if "experience" in parsed_json and parsed_json["experience"]:
        latex += r"\section{Experience}" + "\n"
        latex += r"\resumeSubHeadingListStart" + "\n"
        for exp in parsed_json["experience"]:
            latex += r"  \resumeSubheading" + "\n"
            latex += f"    {{{escape(exp.get('title', ''))}}}{{{escape(exp.get('dates', ''))}}}\n"
            latex += f"    {{{escape(exp.get('company', ''))}}}{{}}\n"
            if exp.get("bullets"):
                latex += r"    \resumeItemListStart" + "\n"
                for bullet in exp["bullets"]:
                    latex += f"        \\resumeItem{{{escape(bullet)}}}\n"
                latex += r"    \resumeItemListEnd" + "\n"
        latex += r"\resumeSubHeadingListEnd" + "\n\n"

    # Projects
    if "projects" in parsed_json and parsed_json["projects"]:
        latex += r"\section{Projects}" + "\n"
        latex += r"\resumeSubHeadingListStart" + "\n"
        for proj in parsed_json["projects"]:
            proj_name = escape(proj.get('name', ''))
            proj_github = proj.get('github_url', '') or proj.get('github', '')
            if proj_github:
                proj_github_url = proj_github if proj_github.startswith('http') else f'https://{proj_github}'
                proj_heading = f"\\textbf{{{proj_name}}} \\href{{{proj_github_url}}}{{[\\underline{{GitHub}}]}}"
            else:
                proj_heading = f"\\textbf{{{proj_name}}}"
            latex += r"  \resumeProjectHeading" + "\n"
            latex += f"    {{{proj_heading}}}{{}}\n"
            if proj.get("bullets"):
                latex += r"    \resumeItemListStart" + "\n"
                for bullet in proj["bullets"]:
                    latex += f"        \\resumeItem{{{escape(bullet)}}}\n"
                latex += r"    \resumeItemListEnd" + "\n"
        latex += r"\resumeSubHeadingListEnd" + "\n\n"

    # Skills — render by category if entries contain ":" separators
    if "skills" in parsed_json and parsed_json["skills"]:
        latex += r"\section{Technical Skills}" + "\n"
        latex += r"\begin{itemize}[leftmargin=0.15in, label={}]" + "\n"
        latex += r"  \small{\item{" + "\n"
        skills_list = parsed_json["skills"]
        if isinstance(skills_list, list) and len(skills_list) > 0 and isinstance(skills_list[0], str) and ":" in skills_list[0]:
            # Category-based: ["GenAI/LLM: RAG, Prompt Engineering, ...", ...]
            for skill_line in skills_list:
                if ":" in skill_line:
                    cat, items = skill_line.split(":", 1)
                    latex += f"    \\textbf{{{escape(cat.strip())}}}{{: {escape(items.strip())}}} \\\\\n"
                else:
                    latex += f"    {escape(skill_line)} \\\\\n"
        elif isinstance(skills_list, dict):
            # Dict-based: {"GenAI/LLM": ["RAG", ...], ...}
            for cat, items in skills_list.items():
                if isinstance(items, list):
                    latex += f"    \\textbf{{{escape(cat)}}}{{: {escape(', '.join(items))}}} \\\\\n"
                else:
                    latex += f"    \\textbf{{{escape(cat)}}}{{: {escape(str(items))}}} \\\\\n"
        else:
            latex += r"    \textbf{Skills}{: " + escape(", ".join(str(s) for s in skills_list)) + r"}" + "\n"
        latex += r"  }}" + "\n"
        latex += r"\end{itemize}" + "\n"

    # Certifications & Achievements
    certs = parsed_json.get("certifications", [])
    achs = parsed_json.get("achievements", [])
    if certs or achs:
        latex += r"\section{Certifications \& Achievements}" + "\n"
        latex += r"\resumeItemListStart" + "\n"
        for item in certs + achs:
            latex += f"  \\resumeItem{{{escape(item)}}}\n"
        latex += r"\resumeItemListEnd" + "\n\n"

    latex += r"\end{document}" + "\n"
    return latex
