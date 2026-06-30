import React, { useState, useEffect } from 'react'
import StageCard from './components/StageCard'
import CandidateTable from './components/CandidateTable'
import {
  uploadCandidates,
  evaluateCandidates,
  getCandidates,
  shortlistCandidates,
  uploadTestResults,
  scheduleInterviews,
} from './api'

export default function App() {
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState({})
  const [logs, setLogs] = useState([])

  const [candidateFile, setCandidateFile] = useState(null)
  const [jobDescription, setJobDescription] = useState('')
  const [testLink, setTestLink] = useState('')
  const [shortlistThreshold, setShortlistThreshold] = useState(60)
  const [testResultsFile, setTestResultsFile] = useState(null)
  const [interviewThreshold, setInterviewThreshold] = useState(70)

  const log = (msg, type = 'info') => {
    setLogs((prev) => [{ msg, type, time: new Date().toLocaleTimeString() }, ...prev].slice(0, 8))
  }

  const refresh = async () => {
    try {
      const res = await getCandidates()
      setCandidates(res.data)
    } catch (e) {
      log('Could not load candidates — is the backend running?', 'error')
    }
  }

  useEffect(() => { refresh() }, [])

  const withLoading = async (key, fn) => {
    setLoading((p) => ({ ...p, [key]: true }))
    try {
      await fn()
    } catch (e) {
      log(e.response?.data?.detail || e.message, 'error')
    } finally {
      setLoading((p) => ({ ...p, [key]: false }))
      refresh()
    }
  }

  const stage1Status = candidates.length ? 'done' : 'idle'
  const stage2Status = candidates.some(c => c.jd_score != null) ? 'done' : (candidates.length ? 'active' : 'idle')
  const stage3Status = candidates.some(c => c.status === 'shortlisted' || c.status === 'tested' || c.status === 'interview_scheduled') ? 'done' : (stage2Status === 'done' ? 'active' : 'idle')
  const stage4Status = candidates.some(c => c.test_la_score != null) ? 'done' : (stage3Status === 'done' ? 'active' : 'idle')
  const stage5Status = candidates.some(c => c.status === 'interview_scheduled') ? 'done' : (stage4Status === 'done' ? 'active' : 'idle')

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-line bg-white/40 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-baseline justify-between">
          <div>
            <h1 className="font-display text-2xl text-ink">Visl</h1>
            <p className="text-xs text-ink/50 step-num uppercase tracking-wide">AI Candidate Screening Pipeline</p>
          </div>
          <div className="text-sm text-ink/60">
            {candidates.length} candidate{candidates.length !== 1 ? 's' : ''} loaded
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-10">
        <div>
          {/* Stage 1: Upload */}
          <StageCard
            number="01"
            title="Upload candidate dataset"
            description="CSV or XLSX with s_no, name, email, college, branch, cgpa, best_ai_project, research_work, github, resume"
            status={stage1Status}
          >
            <div className="flex items-center gap-3">
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(e) => setCandidateFile(e.target.files[0])}
                className="text-sm text-ink/70 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-ink file:text-paper file:text-xs file:cursor-pointer"
              />
              <button
                disabled={!candidateFile || loading.upload}
                onClick={() => withLoading('upload', async () => {
                  const res = await uploadCandidates(candidateFile)
                  log(`Uploaded ${res.data.added} candidates (${res.data.skipped_duplicates} duplicates skipped)`)
                })}
                className="text-sm bg-moss text-white px-4 py-1.5 rounded disabled:opacity-30 hover:bg-moss2 transition-colors"
              >
                {loading.upload ? 'Uploading…' : 'Upload'}
              </button>
            </div>
          </StageCard>

          {/* Stage 2: JD + Evaluate */}
          <StageCard
            number="02"
            title="Provide job description & evaluate"
            description="Resumes are downloaded and parsed, then scored against this JD by Claude. GitHub profiles are analyzed in parallel."
            status={stage2Status}
          >
            <textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the job description here…"
              rows={4}
              className="w-full text-sm border border-line rounded p-3 mb-3 bg-white/70 focus:outline-none focus:ring-2 focus:ring-moss/30"
            />
            <button
              disabled={!jobDescription || !candidates.length || loading.evaluate}
              onClick={() => withLoading('evaluate', async () => {
                const res = await evaluateCandidates(jobDescription)
                log(`Evaluated ${res.data.count} candidates against JD + GitHub`)
              })}
              className="text-sm bg-moss text-white px-4 py-1.5 rounded disabled:opacity-30 hover:bg-moss2 transition-colors"
            >
              {loading.evaluate ? 'Evaluating…' : 'Run AI Evaluation'}
            </button>
          </StageCard>

          {/* Stage 3: Shortlist + send test */}
          <StageCard
            number="03"
            title="Score, rank & send assessments"
            description="Candidates above the threshold receive an automated email with the test link."
            status={stage3Status}
          >
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-xs text-ink/60 step-num">Threshold</label>
              <input
                type="number"
                value={shortlistThreshold}
                onChange={(e) => setShortlistThreshold(e.target.value)}
                className="w-16 text-sm border border-line rounded px-2 py-1 bg-white/70"
              />
              <input
                type="text"
                value={testLink}
                onChange={(e) => setTestLink(e.target.value)}
                placeholder="https://your-test-platform.com/assessment/xyz"
                className="flex-1 min-w-[200px] text-sm border border-line rounded px-3 py-1.5 bg-white/70"
              />
              <button
                disabled={!testLink || loading.shortlist}
                onClick={() => withLoading('shortlist', async () => {
                  const res = await shortlistCandidates(shortlistThreshold, testLink)
                  log(`Shortlisted & emailed ${res.data.shortlisted} candidates`)
                })}
                className="text-sm bg-moss text-white px-4 py-1.5 rounded disabled:opacity-30 hover:bg-moss2 transition-colors"
              >
                {loading.shortlist ? 'Sending…' : 'Shortlist & Send'}
              </button>
            </div>
          </StageCard>

          {/* Stage 4: Upload test results */}
          <StageCard
            number="04"
            title="Upload test results"
            description="CSV or XLSX with s_no, test_la, test_code. Matched to candidates by s_no, blended 50/50 into the final score."
            status={stage4Status}
          >
            <div className="flex items-center gap-3">
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(e) => setTestResultsFile(e.target.files[0])}
                className="text-sm text-ink/70 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-ink file:text-paper file:text-xs file:cursor-pointer"
              />
              <button
                disabled={!testResultsFile || loading.testResults}
                onClick={() => withLoading('testResults', async () => {
                  const res = await uploadTestResults(testResultsFile)
                  log(`Updated test scores for ${res.data.updated_count} candidates`)
                })}
                className="text-sm bg-moss text-white px-4 py-1.5 rounded disabled:opacity-30 hover:bg-moss2 transition-colors"
              >
                {loading.testResults ? 'Uploading…' : 'Upload Results'}
              </button>
            </div>
          </StageCard>

          {/* Stage 5: Schedule interviews */}
          <StageCard
            number="05"
            title="Schedule interviews"
            description="Qualified candidates get a real Google Calendar event with an auto-generated Meet link, plus an email invite."
            status={stage5Status}
          >
            <div className="flex items-center gap-3">
              <label className="text-xs text-ink/60 step-num">Threshold</label>
              <input
                type="number"
                value={interviewThreshold}
                onChange={(e) => setInterviewThreshold(e.target.value)}
                className="w-16 text-sm border border-line rounded px-2 py-1 bg-white/70"
              />
              <button
                disabled={loading.schedule}
                onClick={() => withLoading('schedule', async () => {
                  const res = await scheduleInterviews(interviewThreshold)
                  log(`Scheduled ${res.data.scheduled_count} interviews with Meet links`)
                })}
                className="text-sm bg-clay text-white px-4 py-1.5 rounded disabled:opacity-30 hover:opacity-90 transition-colors"
              >
                {loading.schedule ? 'Scheduling…' : 'Schedule Interviews'}
              </button>
            </div>
          </StageCard>
        </div>

        {/* Sidebar: ranking table + activity log */}
        <aside className="lg:sticky lg:top-24 self-start space-y-6">
          <div className="bg-white/60 border border-line rounded-lg p-5">
            <h3 className="font-display text-lg mb-3">Ranked candidates</h3>
            <CandidateTable candidates={candidates} />
          </div>

          {logs.length > 0 && (
            <div className="bg-white/60 border border-line rounded-lg p-4">
              <h4 className="step-num text-xs uppercase tracking-wide text-ink/50 mb-2">Activity</h4>
              <ul className="space-y-1.5">
                {logs.map((l, i) => (
                  <li key={i} className={`text-xs ${l.type === 'error' ? 'text-clay' : 'text-ink/60'}`}>
                    <span className="step-num text-ink/30 mr-1">{l.time}</span>{l.msg}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </main>
    </div>
  )
}
