"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function UploadPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);
  const [jdText, setJdText] = useState("");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !jdText || !company || !role) {
      alert("Please fill all fields");
      return;
    }

    setLoading(true);
    
    try {
      // 1. Upload Resume
      const formData = new FormData();
      formData.append("file", file);
      const resumeRes = await fetch(`http://127.0.0.1:8000/resumes/upload?label=${encodeURIComponent(role + " Resume")}`, {
        method: "POST",
        body: formData,
      });
      const resumeData = await resumeRes.json();
      
      if (!resumeRes.ok) throw new Error(resumeData.detail || "Failed to upload resume");

      // 2. Create Application
      const appRes = await fetch(`http://127.0.0.1:8000/applications?resume_id=${resumeData.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: 1,
          company,
          role_title: role,
          jd_text: jdText
        })
      });
      const appData = await appRes.json();
      
      if (!appRes.ok) throw new Error(appData.detail || "Failed to create application");

      // 3. Run Matching
      await fetch(`http://127.0.0.1:8000/applications/${appData.id}/match`, {
        method: "POST"
      });

      // Redirect to tailoring view
      router.push(`/applications/${appData.id}`);
      
    } catch (err) {
      console.error(err);
      alert(err.message || "An error occurred");
      setLoading(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: '800px' }}>
      <h1 style={{ marginBottom: '10px' }}>New Application</h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '30px' }}>Upload your resume and the job description to calculate your ATS score and start tailoring.</p>
      
      <form onSubmit={handleSubmit} className="glass-panel">
        <div className="input-group">
          <label>Company Name</label>
          <input 
            type="text" 
            className="input-field" 
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="e.g. Acme Corp" 
            required
          />
        </div>
        
        <div className="input-group">
          <label>Role Title</label>
          <input 
            type="text" 
            className="input-field" 
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="e.g. Senior Software Engineer" 
            required
          />
        </div>

        <div className="input-group">
          <label>Upload Resume (PDF or DOCX)</label>
          <input 
            type="file" 
            className="input-field" 
            accept=".pdf,.docx"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            required
          />
        </div>

        <div className="input-group">
          <label>Job Description</label>
          <textarea 
            className="input-field" 
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the full job description here..."
            required
          />
        </div>

        <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '10px' }} disabled={loading}>
          {loading ? "Analyzing and Scoring (This takes a moment)..." : "Analyze Application"}
        </button>
      </form>
    </div>
  );
}
