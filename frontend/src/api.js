import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: API_URL })

export const uploadCandidates = (file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/upload-candidates', form)
}

export const evaluateCandidates = (jobDescription) => {
  const form = new FormData()
  form.append('job_description', jobDescription)
  return api.post('/evaluate', form)
}

export const getCandidates = () => api.get('/candidates')

export const shortlistCandidates = (threshold, testLink) => {
  const form = new FormData()
  form.append('threshold', threshold)
  form.append('test_link', testLink)
  return api.post('/shortlist', form)
}

export const uploadTestResults = (file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/upload-test-results', form)
}

export const scheduleInterviews = (threshold) => {
  const form = new FormData()
  form.append('threshold', threshold)
  return api.post('/schedule-interviews', form)
}

export default api
