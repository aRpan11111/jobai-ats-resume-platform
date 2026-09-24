"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function Dashboard() {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/applications")
      .then(res => res.json())
      .then(data => {
        setApplications(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
        <h1 style={{ fontSize: '2.5rem', fontWeight: 700 }}>Tracker Board</h1>
        <Link href="/upload" className="btn btn-primary">+ New Application</Link>
      </div>

      {loading ? (
        <p>Loading applications...</p>
      ) : applications.length === 0 ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <h3 style={{ marginBottom: '10px' }}>No applications yet</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>Upload a resume and job description to get started.</p>
          <Link href="/upload" className="btn btn-primary">Start Tailoring</Link>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
          {applications.map(app => (
            <div key={app.id} className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{new Date(app.created_at).toLocaleDateString()}</span>
                <span style={{ 
                  background: 'rgba(255, 255, 255, 0.1)', 
                  padding: '4px 8px', 
                  borderRadius: '12px', 
                  fontSize: '0.8rem',
                  textTransform: 'capitalize'
                }}>
                  {app.status}
                </span>
              </div>
              <h3 style={{ fontSize: '1.2rem', marginBottom: '4px' }}>{app.role_title}</h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '15px' }}>{app.company}</p>
              
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '8px', marginBottom: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.9rem' }}>ATS Match Score</span>
                  <span style={{ fontWeight: 600, color: app.ats_score && app.ats_score > 75 ? 'var(--success-color)' : 'var(--warning-color)' }}>
                    {app.ats_score ? `${app.ats_score.toFixed(1)}%` : 'Pending'}
                  </span>
                </div>
                <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ 
                    width: `${app.ats_score || 0}%`, 
                    height: '100%', 
                    background: app.ats_score && app.ats_score > 75 ? 'var(--success-color)' : 'var(--warning-color)',
                    transition: 'width 1s ease'
                  }}></div>
                </div>
              </div>

              <Link href={`/applications/${app.id}`} className="btn btn-secondary" style={{ width: '100%' }}>
                View & Tailor
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
