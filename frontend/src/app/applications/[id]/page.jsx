"use client";

import { useEffect, useState, use, useCallback, useRef } from "react";

export default function TailoringPage({ params }) {
  const unwrappedParams = use(params);
  const id = unwrappedParams.id;

  // --- Core data state ---
  const [appData, setAppData] = useState(null);
  const [scoreData, setScoreData] = useState(null);
  const [originalScore, setOriginalScore] = useState(null);
  const [loading, setLoading] = useState(true);

  // --- Local resume state (mutable copy for instant updates) ---
  const [localResume, setLocalResume] = useState(null);

  // --- Click-to-edit state ---
  const [selectedBulletId, setSelectedBulletId] = useState(null);
  const [pendingSuggestion, setPendingSuggestion] = useState(null);
  const [loadingSuggestion, setLoadingSuggestion] = useState(false);
  const [editedBullets, setEditedBullets] = useState(new Set());

  // --- Summary & Skills tailoring state ---
  const [summarySuggestion, setSummarySuggestion] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [editedSummary, setEditedSummary] = useState(false);

  const [skillsSuggestion, setSkillsSuggestion] = useState(null);
  const [loadingSkills, setLoadingSkills] = useState(false);
  const [editedSkills, setEditedSkills] = useState(false);

  // Track which bullet ID the in-flight request is for (concurrency guard)
  const inflightBulletRef = useRef(null);

  // --- Load application data ---
  const loadData = useCallback(async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/applications`);
      const allApps = await res.json();
      const current = allApps.find((a) => a.id.toString() === id);

      const resumeRes = await fetch(`http://127.0.0.1:8000/applications/${id}/resume`);
      const resumeData = await resumeRes.json();

      setAppData({ ...current, parsed_json: resumeData });

      // Initialize local resume from server data
      let parsed = resumeData;
      if (typeof parsed === "string") {
        try { parsed = JSON.parse(parsed); } catch { parsed = null; }
      }
      if (parsed && Object.keys(parsed).length === 0) parsed = null;
      setLocalResume(parsed);

      const matchRes = await fetch(`http://127.0.0.1:8000/applications/${id}/match`, { method: "POST" });
      const matchDetails = await matchRes.json();
      setScoreData(matchDetails);

      // Capture original score only once (first load)
      setOriginalScore((prev) => prev === null ? matchDetails.ats_score : prev);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // --- Click a bullet to request AI rewrite ---
  const handleBulletClick = async (bulletId, bulletText, section, itemName) => {
    if (selectedBulletId === bulletId) {
      setSelectedBulletId(null);
      setPendingSuggestion(null);
      inflightBulletRef.current = null;
      return;
    }

    setSelectedBulletId(bulletId);
    setPendingSuggestion(null);
    setLoadingSuggestion(true);
    inflightBulletRef.current = bulletId;

    try {
      const res = await fetch(`http://127.0.0.1:8000/applications/${id}/bullet-rewrite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bullet_id: bulletId,
          bullet_text: bulletText,
          section: section,
          item_name: itemName,
        }),
      });

      const data = await res.json();

      if (inflightBulletRef.current === bulletId) {
        setPendingSuggestion({
          bulletId: data.bullet_id,
          originalText: bulletText,
          suggestedText: data.suggested_bullet,
          reasoning: data.reasoning,
        });
      }
    } catch (e) {
      console.error("Bullet rewrite failed:", e);
    } finally {
      if (inflightBulletRef.current === bulletId) {
        setLoadingSuggestion(false);
      }
    }
  };

  // --- Accept a bullet suggestion ---
  const handleAccept = async () => {
    if (!pendingSuggestion) return;

    const { bulletId, suggestedText } = pendingSuggestion;

    const parts = bulletId.split("-");
    const section = parts[0];
    const itemIdx = parseInt(parts[1]);
    const bulletIdx = parseInt(parts[2]);

    setLocalResume((prev) => {
      if (!prev) return prev;
      const updated = JSON.parse(JSON.stringify(prev));
      const items = updated[section];
      if (items && items[itemIdx] && items[itemIdx].bullets && items[itemIdx].bullets[bulletIdx] !== undefined) {
        items[itemIdx].bullets[bulletIdx] = suggestedText;
      }
      return updated;
    });

    setEditedBullets((prev) => new Set(prev).add(bulletId));
    setSelectedBulletId(null);
    setPendingSuggestion(null);
    inflightBulletRef.current = null;

    try {
      const res = await fetch(`http://127.0.0.1:8000/applications/${id}/bullet-accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bullet_id: bulletId,
          new_text: suggestedText,
        }),
      });
      const data = await res.json();

      if (data.score_data) {
        setScoreData(data.score_data);
      } else if (data.new_score !== undefined) {
        setScoreData((prev) => ({ ...prev, ats_score: data.new_score }));
      }
    } catch (e) {
      console.error("Accept failed:", e);
    }
  };

  // --- Reject a bullet suggestion ---
  const handleReject = () => {
    setSelectedBulletId(null);
    setPendingSuggestion(null);
    inflightBulletRef.current = null;
  };

  // --- Summary Tailoring Handlers ---
  const handleTailorSummary = async () => {
    if (loadingSummary) return;
    setLoadingSummary(true);
    setSummarySuggestion(null);
    try {
      const res = await fetch(`http://127.0.0.1:8000/applications/${id}/tailor-summary`, { method: "POST" });
      const data = await res.json();
      setSummarySuggestion({
        originalSummary: localResume?.summary || "",
        suggestedSummary: data.suggested_summary,
        reasoning: data.reasoning,
      });
    } catch (e) {
      console.error("Summary tailoring failed:", e);
    } finally {
      setLoadingSummary(false);
    }
  };

  const handleAcceptSummary = async () => {
    if (!summarySuggestion) return;
    const { suggestedSummary } = summarySuggestion;

    setLocalResume((prev) => ({
      ...prev,
      summary: suggestedSummary,
    }));
    setEditedSummary(true);
    setSummarySuggestion(null);

    try {
      const res = await fetch(`http://127.0.0.1:8000/applications/${id}/accept-summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_summary: suggestedSummary }),
      });
      const data = await res.json();
      if (data.score_data) {
        setScoreData(data.score_data);
      }
    } catch (e) {
      console.error("Accept summary failed:", e);
    }
  };

  const handleRejectSummary = () => {
    setSummarySuggestion(null);
  };

  // --- Skills Tailoring Handlers ---
  const handleTailorSkills = async () => {
    if (loadingSkills) return;
    setLoadingSkills(true);
    setSkillsSuggestion(null);
    try {
      const res = await fetch(`http://127.0.0.1:8000/applications/${id}/tailor-skills`, { method: "POST" });
      const data = await res.json();
      setSkillsSuggestion({
        originalSkills: localResume?.skills || [],
        suggestedSkills: data.suggested_skills,
        missingJdSkills: data.missing_jd_skills,
        reasoning: data.reasoning,
      });
    } catch (e) {
      console.error("Skills tailoring failed:", e);
    } finally {
      setLoadingSkills(false);
    }
  };

  const handleAcceptSkills = async () => {
    if (!skillsSuggestion) return;
    const { suggestedSkills } = skillsSuggestion;

    setLocalResume((prev) => ({
      ...prev,
      skills: suggestedSkills,
    }));
    setEditedSkills(true);
    setSkillsSuggestion(null);

    try {
      const res = await fetch(`http://127.0.0.1:8000/applications/${id}/accept-skills`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_skills: suggestedSkills }),
      });
      const data = await res.json();
      if (data.score_data) {
        setScoreData(data.score_data);
      }
    } catch (e) {
      console.error("Accept skills failed:", e);
    }
  };

  const handleRejectSkills = () => {
    setSkillsSuggestion(null);
  };

  // --- Render ---
  if (loading) return <div className="container"><p>Loading...</p></div>;
  if (!appData) return <div className="container"><p>Application not found.</p></div>;

  const parsedResume = localResume;
  const currentScore = scoreData?.ats_score ?? 0;
  const scoreDelta = originalScore !== null ? currentScore - originalScore : 0;

  // --- Bullet renderer (used by both Experience and Projects) ---
  const renderBullet = (bullet, bulletId, section, itemName) => {
    const isSelected = selectedBulletId === bulletId;
    const isEdited = editedBullets.has(bulletId);
    const hasPendingSuggestion = pendingSuggestion?.bulletId === bulletId;
    const isLoadingThis = isSelected && loadingSuggestion;

    return (
      <li
        key={bulletId}
        onClick={(e) => {
          e.stopPropagation();
          if (!loadingSuggestion || isSelected) {
            handleBulletClick(bulletId, bullet, section, itemName);
          }
        }}
        style={{
          marginBottom: hasPendingSuggestion ? '4px' : '6px',
          fontSize: '0.95rem',
          padding: '8px 10px',
          borderRadius: '6px',
          cursor: loadingSuggestion && !isSelected ? 'wait' : 'pointer',
          transition: 'all 0.2s ease',
          borderLeft: isSelected
            ? '3px solid var(--primary-color)'
            : isEdited
              ? '3px solid var(--success-color)'
              : '3px solid transparent',
          background: isSelected
            ? 'rgba(99, 102, 241, 0.08)'
            : 'transparent',
          position: 'relative',
        }}
        onMouseEnter={(e) => {
          if (!isSelected) {
            e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
            e.currentTarget.style.borderLeftColor = 'rgba(99,102,241,0.4)';
          }
        }}
        onMouseLeave={(e) => {
          if (!isSelected) {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.borderLeftColor = isEdited ? 'var(--success-color)' : 'transparent';
          }
        }}
      >
        <span>{bullet}</span>

        {isEdited && !isSelected && (
          <span style={{
            marginLeft: '8px',
            fontSize: '0.7rem',
            color: 'var(--success-color)',
            background: 'rgba(34, 197, 94, 0.1)',
            padding: '2px 6px',
            borderRadius: '4px',
            verticalAlign: 'middle',
          }}>
            ✏️ Edited
          </span>
        )}

        {/* Loading spinner */}
        {isLoadingThis && (
          <div style={{
            marginTop: '12px',
            padding: '15px',
            background: 'rgba(30, 41, 59, 0.95)',
            borderRadius: '8px',
            borderLeft: '4px solid var(--primary-color)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}>
            <div style={{
              width: '16px', height: '16px',
              border: '2px solid rgba(99,102,241,0.3)',
              borderTop: '2px solid var(--primary-color)',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
            }} />
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Generating AI suggestion...
            </span>
          </div>
        )}

        {/* Suggestion card */}
        {hasPendingSuggestion && pendingSuggestion && (
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              marginTop: '12px',
              padding: '16px',
              background: 'rgba(30, 41, 59, 0.95)',
              borderRadius: '8px',
              borderLeft: '4px solid var(--primary-color)',
              backdropFilter: 'blur(8px)',
            }}
          >
            <div style={{
              fontSize: '0.75rem',
              color: 'var(--text-secondary)',
              marginBottom: '10px',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              <span>✨ AI Suggestion</span>
              <span style={{ color: 'var(--primary-color)', fontWeight: 600 }}>ATS Optimized</span>
            </div>

            <div style={{
              fontSize: '0.88rem',
              color: '#ef4444',
              opacity: 0.7,
              textDecoration: 'line-through',
              marginBottom: '8px',
              lineHeight: '1.5',
            }}>
              − {pendingSuggestion.originalText}
            </div>

            <div style={{
              fontSize: '0.88rem',
              color: '#86efac',
              marginBottom: '10px',
              lineHeight: '1.5',
            }}>
              + {pendingSuggestion.suggestedText}
            </div>

            {pendingSuggestion.reasoning && (
              <div style={{
                fontSize: '0.8rem',
                color: 'var(--text-secondary)',
                fontStyle: 'italic',
                marginBottom: '12px',
                padding: '8px',
                background: 'rgba(255,255,255,0.03)',
                borderRadius: '4px',
              }}>
                💡 {pendingSuggestion.reasoning}
              </div>
            )}

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                className="btn btn-primary"
                style={{ padding: '6px 16px', fontSize: '0.8rem' }}
                onClick={(e) => { e.stopPropagation(); handleAccept(); }}
              >
                ✅ Accept
              </button>
              <button
                className="btn btn-secondary"
                style={{ padding: '6px 16px', fontSize: '0.8rem' }}
                onClick={(e) => { e.stopPropagation(); handleReject(); }}
              >
                ❌ Reject
              </button>
            </div>
          </div>
        )}
      </li>
    );
  };

  // --- Helper to render skills by category ---
  const renderSkills = (skills) => {
    if (!skills || (Array.isArray(skills) && skills.length === 0)) return null;

    if (Array.isArray(skills) && typeof skills[0] === 'string' && skills[0].includes(':')) {
      return (
        <div style={{ fontSize: '0.95rem' }}>
          {skills.map((line, i) => {
            const colonIdx = line.indexOf(':');
            if (colonIdx === -1) return <div key={i}>{line}</div>;
            const category = line.slice(0, colonIdx).trim();
            const items = line.slice(colonIdx + 1).trim();
            return (
              <div key={i} style={{ marginBottom: '4px' }}>
                <strong style={{ color: '#fff' }}>{category}:</strong> {items}
              </div>
            );
          })}
        </div>
      );
    }

    if (typeof skills === 'object' && !Array.isArray(skills)) {
      return (
        <div style={{ fontSize: '0.95rem' }}>
          {Object.entries(skills).map(([cat, items], i) => (
            <div key={i} style={{ marginBottom: '4px' }}>
              <strong style={{ color: '#fff' }}>{cat}:</strong> {Array.isArray(items) ? items.join(', ') : String(items)}
            </div>
          ))}
        </div>
      );
    }

    return <p style={{ fontSize: '0.95rem' }}>{skills.join(", ")}</p>;
  };

  return (
    <div className="container" style={{ maxWidth: '1400px', margin: '0 auto', padding: '20px' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
        <div>
          <h1 style={{ marginBottom: '5px' }}>{appData.role_title}</h1>
          <p style={{ color: 'var(--text-secondary)' }}>at {appData.company}</p>
        </div>
        <div>
          <a href={`http://127.0.0.1:8000/applications/${id}/export-pdf`} target="_blank" rel="noopener noreferrer" className="btn btn-primary" style={{ marginRight: '10px' }}>
            📄 Preview PDF
          </a>
          <a href={`http://127.0.0.1:8000/applications/${id}/export`} className="btn btn-secondary">
            Download PDF
          </a>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: '30px' }}>

        {/* Left Column: ATS Analysis */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="glass-panel">
            <h2 style={{ marginBottom: '20px' }}>ATS Match Analysis</h2>

            <div style={{ textAlign: 'center', marginBottom: '30px' }}>
              <div style={{
                fontSize: '4.5rem',
                fontWeight: 700,
                color: currentScore > 75 ? 'var(--success-color)' : 'var(--warning-color)',
                transition: 'color 0.3s ease',
              }}>
                {currentScore.toFixed(1)}%
              </div>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '8px' }}>Current Match</p>

              {/* Before/After delta */}
              {originalScore !== null && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  background: scoreDelta > 0 ? 'rgba(34, 197, 94, 0.1)' : scoreDelta < 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(255,255,255,0.05)',
                  border: `1px solid ${scoreDelta > 0 ? 'rgba(34, 197, 94, 0.3)' : scoreDelta < 0 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(255,255,255,0.1)'}`,
                  marginTop: '8px',
                }}>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    Before: {originalScore.toFixed(1)}%
                  </span>
                  <span style={{ fontSize: '1.1rem', color: 'var(--text-secondary)' }}>→</span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fff' }}>
                    After: {currentScore.toFixed(1)}%
                  </span>
                  <span style={{
                    fontSize: '0.85rem',
                    fontWeight: 700,
                    color: scoreDelta > 0 ? 'var(--success-color)' : scoreDelta < 0 ? '#ef4444' : 'var(--text-secondary)',
                  }}>
                    ({scoreDelta > 0 ? '+' : ''}{scoreDelta.toFixed(1)}%)
                  </span>
                </div>
              )}
            </div>

            <div style={{ marginBottom: '15px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <span>Keyword Coverage</span>
                <span>{scoreData?.keyword_coverage_pct?.toFixed(1)}%</span>
              </div>
              <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px' }}>
                <div style={{ width: `${scoreData?.keyword_coverage_pct}%`, height: '100%', background: 'var(--primary-color)', borderRadius: '3px', transition: 'width 0.5s ease' }}></div>
              </div>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <span>Semantic Coverage</span>
                <span>{scoreData?.semantic_coverage_pct?.toFixed(1)}%</span>
              </div>
              <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px' }}>
                <div style={{ width: `${scoreData?.semantic_coverage_pct}%`, height: '100%', background: '#a855f7', borderRadius: '3px', transition: 'width 0.5s ease' }}></div>
              </div>
            </div>

            {/* ISSUE 4 - Render Scorer Logs and Warning Penalties */}
            {scoreData?.score_logs && scoreData.score_logs.length > 0 && (
              <div style={{ marginTop: '20px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '15px' }}>
                <h3 style={{ fontSize: '0.95rem', color: '#f87171', marginBottom: '10px' }}>⚠️ Scorer Warnings & Penalties</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '200px', overflowY: 'auto' }}>
                  {scoreData.score_logs.map((log, idx) => {
                    const isPenalty = log.includes("Penalty");
                    return (
                      <div key={idx} style={{
                        fontSize: '0.8rem',
                        color: isPenalty ? '#fca5a5' : 'var(--text-secondary)',
                        background: isPenalty ? 'rgba(239, 68, 68, 0.05)' : 'rgba(255,255,255,0.02)',
                        padding: '6px 10px',
                        borderRadius: '4px',
                        borderLeft: `3px solid ${isPenalty ? '#ef4444' : 'rgba(255,255,255,0.2)'}`
                      }}>
                        {log}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {scoreData?.gaps && scoreData.gaps.length > 0 && (
              <>
                <h3 style={{ fontSize: '1.1rem', marginTop: '20px', marginBottom: '15px', color: '#fca5a5' }}>Critical Gaps Detected</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {scoreData.gaps.map((gap, i) => (
                    <div key={i} style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#fca5a5', padding: '10px', borderRadius: '6px', fontSize: '0.9rem' }}>
                      {gap}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="glass-panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '1rem', marginBottom: '10px', color: 'var(--primary-color)' }}>💡 How to use</h3>
            <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.8' }}>
              <li>Click any bullet point to get an AI-optimized version</li>
              <li>Click the <strong>✨ Tailor</strong> button next to <strong>Summary</strong> or <strong>Technical Skills</strong> to run targeted AI section alignment</li>
              <li>Review the suggestion and click <strong>Accept</strong> or <strong>Reject</strong></li>
            </ul>
          </div>
        </div>

        {/* Right Column: Interactive Resume Preview */}
        <div className="glass-panel" style={{ padding: '40px', background: '#0f172a' }}>
          {!parsedResume ? (
            <p style={{ color: 'var(--text-secondary)', textAlign: 'center' }}>No structured data available to render.</p>
          ) : (
            <div style={{ color: '#e2e8f0', lineHeight: '1.6' }}>
              {/* Header */}
              <div style={{ textAlign: 'center', marginBottom: '30px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '20px' }}>
                <h1 style={{ fontSize: '2.5rem', marginBottom: '10px', color: '#fff' }}>
                  {parsedResume.contact_info?.name || 'Candidate'}
                </h1>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', display: 'flex', justifyContent: 'center', gap: '15px', flexWrap: 'wrap' }}>
                  {parsedResume.contact_info?.phone && <span>{parsedResume.contact_info.phone}</span>}
                  {parsedResume.contact_info?.email && <span>{parsedResume.contact_info.email}</span>}
                  {parsedResume.contact_info?.linkedin && (
                    <a href={parsedResume.contact_info.linkedin.startsWith('http') ? parsedResume.contact_info.linkedin : `https://${parsedResume.contact_info.linkedin}`}
                       target="_blank" rel="noopener noreferrer"
                       style={{ color: 'var(--primary-color)', textDecoration: 'underline' }}>
                      {parsedResume.contact_info.linkedin}
                    </a>
                  )}
                  {parsedResume.contact_info?.github && (
                    <a href={parsedResume.contact_info.github.startsWith('http') ? parsedResume.contact_info.github : `https://${parsedResume.contact_info.github}`}
                       target="_blank" rel="noopener noreferrer"
                       style={{ color: 'var(--primary-color)', textDecoration: 'underline' }}>
                      {parsedResume.contact_info.github}
                    </a>
                  )}
                </div>
              </div>

              {/* Summary Section (With Tailoring support) */}
              {parsedResume.summary && (
                <div style={{ marginBottom: '25px', position: 'relative' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.2)', paddingBottom: '5px', marginBottom: '10px' }}>
                    <h2 style={{ fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px', color: '#fff', margin: 0 }}>Summary</h2>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '4px 10px', fontSize: '0.75rem', borderRadius: '4px' }}
                      onClick={handleTailorSummary}
                      disabled={loadingSummary}
                    >
                      {loadingSummary ? "Rewriting..." : "✨ Tailor Summary"}
                    </button>
                  </div>
                  
                  <p style={{ fontSize: '0.95rem', margin: 0, opacity: summarySuggestion ? 0.5 : 1 }}>
                    {parsedResume.summary}
                  </p>

                  {/* Summary Edit Badge */}
                  {editedSummary && !summarySuggestion && (
                    <span style={{
                      display: 'inline-block',
                      marginTop: '6px',
                      fontSize: '0.7rem',
                      color: 'var(--success-color)',
                      background: 'rgba(34, 197, 94, 0.1)',
                      padding: '2px 6px',
                      borderRadius: '4px'
                    }}>
                      ✏️ Summary Tailored
                    </span>
                  )}

                  {/* Summary Suggestion Card */}
                  {summarySuggestion && (
                    <div style={{
                      marginTop: '12px',
                      padding: '16px',
                      background: 'rgba(30, 41, 59, 0.95)',
                      borderRadius: '8px',
                      borderLeft: '4px solid var(--primary-color)',
                      backdropFilter: 'blur(8px)',
                    }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '8px', textTransform: 'uppercase', display: 'flex', justifyContent: 'space-between' }}>
                        <span>✨ AI Summary Suggestion</span>
                        <span style={{ color: 'var(--primary-color)', fontWeight: 600 }}>JD Aligned</span>
                      </div>
                      
                      <div style={{ fontSize: '0.88rem', color: '#ef4444', opacity: 0.7, textDecoration: 'line-through', marginBottom: '8px' }}>
                        − {summarySuggestion.originalSummary}
                      </div>
                      
                      <div style={{ fontSize: '0.88rem', color: '#86efac', marginBottom: '10px' }}>
                        + {summarySuggestion.suggestedSummary}
                      </div>

                      {summarySuggestion.reasoning && (
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '12px', padding: '8px', background: 'rgba(255,255,255,0.03)', borderRadius: '4px' }}>
                          💡 {summarySuggestion.reasoning}
                        </div>
                      )}

                      <div style={{ display: 'flex', gap: '10px' }}>
                        <button className="btn btn-primary" style={{ padding: '6px 16px', fontSize: '0.8rem' }} onClick={handleAcceptSummary}>Accept Summary</button>
                        <button className="btn btn-secondary" style={{ padding: '6px 16px', fontSize: '0.8rem' }} onClick={handleRejectSummary}>Reject</button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Education */}
              {parsedResume.education && parsedResume.education.length > 0 && (
                <div style={{ marginBottom: '25px' }}>
                  <h2 style={{ fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px', borderBottom: '1px solid rgba(255,255,255,0.2)', paddingBottom: '5px', marginBottom: '15px', color: '#fff' }}>Education</h2>
                  {parsedResume.education.map((edu, i) => (
                    <div key={i} style={{ marginBottom: '10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <strong style={{ color: '#fff' }}>{edu.institution}</strong>
                        <span style={{ fontSize: '0.9rem' }}>{edu.dates}</span>
                      </div>
                      <div style={{ fontSize: '0.95rem', fontStyle: 'italic', color: 'var(--text-secondary)' }}>{edu.degree}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Experience */}
              {parsedResume.experience && parsedResume.experience.length > 0 && (
                <div style={{ marginBottom: '25px' }}>
                  <h2 style={{ fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px', borderBottom: '1px solid rgba(255,255,255,0.2)', paddingBottom: '5px', marginBottom: '15px', color: '#fff' }}>Experience</h2>
                  {parsedResume.experience.map((exp, i) => (
                    <div key={i} style={{ marginBottom: '20px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <strong style={{ color: '#fff', fontSize: '1.05rem' }}>{exp.title}</strong>
                        <span style={{ fontSize: '0.9rem' }}>{exp.dates}</span>
                      </div>
                      <div style={{ fontSize: '0.95rem', fontStyle: 'italic', color: 'var(--text-secondary)', marginBottom: '8px' }}>{exp.company}</div>

                      <ul style={{ paddingLeft: '8px', margin: 0, listStyle: 'none' }}>
                        {exp.bullets && exp.bullets.map((bullet, j) => {
                          const bulletId = `experience-${i}-${j}`;
                          return renderBullet(bullet, bulletId, "experience", exp.title || exp.company || "");
                        })}
                      </ul>
                    </div>
                  ))}
                </div>
              )}

              {/* Projects */}
              {parsedResume.projects && parsedResume.projects.length > 0 && (
                <div style={{ marginBottom: '25px' }}>
                  <h2 style={{ fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px', borderBottom: '1px solid rgba(255,255,255,0.2)', paddingBottom: '5px', marginBottom: '15px', color: '#fff' }}>Projects</h2>
                  {parsedResume.projects.map((proj, i) => {
                    const projGithub = proj.github_url || proj.github || '';
                    return (
                      <div key={i} style={{ marginBottom: '15px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <strong style={{ color: '#fff' }}>{proj.name}</strong>
                          {projGithub && (
                            <a href={projGithub.startsWith('http') ? projGithub : `https://${projGithub}`}
                               target="_blank" rel="noopener noreferrer"
                               style={{ color: 'var(--primary-color)', fontSize: '0.8rem', textDecoration: 'underline' }}>
                              [GitHub]
                            </a>
                          )}
                        </div>
                        <ul style={{ paddingLeft: '8px', margin: '5px 0 0 0', listStyle: 'none' }}>
                          {proj.bullets && proj.bullets.map((bullet, j) => {
                            const bulletId = `projects-${i}-${j}`;
                            return renderBullet(bullet, bulletId, "projects", proj.name || "");
                          })}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Skills Section (With Tailoring support) */}
              {parsedResume.skills && (
                <div style={{ marginBottom: '25px', position: 'relative' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.2)', paddingBottom: '5px', marginBottom: '10px' }}>
                    <h2 style={{ fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px', color: '#fff', margin: 0 }}>Technical Skills</h2>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '4px 10px', fontSize: '0.75rem', borderRadius: '4px' }}
                      onClick={handleTailorSkills}
                      disabled={loadingSkills}
                    >
                      {loadingSkills ? "Optimizing..." : "✨ Tailor Skills"}
                    </button>
                  </div>
                  
                  <div style={{ opacity: skillsSuggestion ? 0.5 : 1 }}>
                    {renderSkills(parsedResume.skills)}
                  </div>

                  {/* Skills Edit Badge */}
                  {editedSkills && !skillsSuggestion && (
                    <span style={{
                      display: 'inline-block',
                      marginTop: '6px',
                      fontSize: '0.7rem',
                      color: 'var(--success-color)',
                      background: 'rgba(34, 197, 94, 0.1)',
                      padding: '2px 6px',
                      borderRadius: '4px'
                    }}>
                      ✏️ Skills Tailored
                    </span>
                  )}

                  {/* Skills Suggestion Card */}
                  {skillsSuggestion && (
                    <div style={{
                      marginTop: '12px',
                      padding: '16px',
                      background: 'rgba(30, 41, 59, 0.95)',
                      borderRadius: '8px',
                      borderLeft: '4px solid var(--primary-color)',
                      backdropFilter: 'blur(8px)',
                    }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '8px', textTransform: 'uppercase', display: 'flex', justifyContent: 'space-between' }}>
                        <span>✨ AI Skills Suggestion</span>
                        <span style={{ color: 'var(--primary-color)', fontWeight: 600 }}>JD Aligned</span>
                      </div>
                      
                      <div style={{ fontSize: '0.88rem', color: '#ef4444', opacity: 0.7, textDecoration: 'line-through', marginBottom: '8px' }}>
                        Original Skills list will be replaced
                      </div>

                      <div style={{ fontSize: '0.88rem', color: '#86efac', marginBottom: '10px' }}>
                        <strong>Suggested Skills:</strong>
                        <div style={{ paddingLeft: '10px', marginTop: '5px' }}>
                          {skillsSuggestion.suggestedSkills.map((line, idx) => (
                            <div key={idx} style={{ fontSize: '0.85rem', marginBottom: '3px' }}>{line}</div>
                          ))}
                        </div>
                      </div>

                      {/* Warnings about completely missing JD skills (Hard constraint verification) */}
                      {skillsSuggestion.missingJdSkills && skillsSuggestion.missingJdSkills.length > 0 && (
                        <div style={{
                          fontSize: '0.8rem',
                          color: '#fca5a5',
                          background: 'rgba(239, 68, 68, 0.1)',
                          padding: '10px',
                          borderRadius: '6px',
                          marginBottom: '12px',
                          borderLeft: '3px solid #ef4444'
                        }}>
                          <strong>⚠️ Skills required by JD but not found in your resume (Omitted to avoid fabrication):</strong>
                          <ul style={{ margin: '5px 0 0 0', paddingLeft: '15px' }}>
                            {skillsSuggestion.missingJdSkills.map((missing, idx) => (
                              <li key={idx}>{missing}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {skillsSuggestion.reasoning && (
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '12px', padding: '8px', background: 'rgba(255,255,255,0.03)', borderRadius: '4px' }}>
                          💡 {skillsSuggestion.reasoning}
                        </div>
                      )}

                      <div style={{ display: 'flex', gap: '10px' }}>
                        <button className="btn btn-primary" style={{ padding: '6px 16px', fontSize: '0.8rem' }} onClick={handleAcceptSkills}>Accept Skills</button>
                        <button className="btn btn-secondary" style={{ padding: '6px 16px', fontSize: '0.8rem' }} onClick={handleRejectSkills}>Reject</button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Certifications & Achievements */}
              {((parsedResume.certifications && parsedResume.certifications.length > 0) || (parsedResume.achievements && parsedResume.achievements.length > 0)) && (
                <div style={{ marginBottom: '25px' }}>
                  <h2 style={{ fontSize: '1.2rem', textTransform: 'uppercase', letterSpacing: '1px', borderBottom: '1px solid rgba(255,255,255,0.2)', paddingBottom: '5px', marginBottom: '10px', color: '#fff' }}>Certifications & Achievements</h2>
                  <ul style={{ paddingLeft: '20px', margin: 0 }}>
                    {(parsedResume.certifications || []).map((cert, i) => (
                      <li key={`cert-${i}`} style={{ marginBottom: '6px', fontSize: '0.95rem' }}>{cert}</li>
                    ))}
                    {(parsedResume.achievements || []).map((ach, i) => (
                      <li key={`ach-${i}`} style={{ marginBottom: '6px', fontSize: '0.95rem' }}>{ach}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
