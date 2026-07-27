'use client';

import { useState } from 'react';

export default function ComplianceCheckPage() {
  const [payload, setPayload] = useState('{\n  "auth": "strict",\n  "encryption": true\n}');
  const [apiKey, setApiKey] = useState('');
  const [regulationId, setRegulationId] = useState('');
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleCheck = async () => {
    setLoading(true);
    setError('');
    setResults(null);
    
    try {
      const parsedPayload = JSON.parse(payload);
      const res = await fetch('http://localhost:8000/api/v1/check-compliance', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {})
        },
        body: JSON.stringify({
          payload: parsedPayload,
          scope: 'system',
          regulation_id: regulationId
        })
      });
      
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error?.message || data.detail || 'Failed to check compliance');
      }
      setResults(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-12 px-6">
      <h1 className="text-3xl font-bold mb-8 text-white">Compliance Tester</h1>
      
      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">API Key</label>
          <input
            type="password"
            className="w-full bg-[#111] border border-gray-800 rounded-md px-4 py-2 text-white"
            placeholder="sk_live_..."
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">Regulation ID (UUID)</label>
          <input
            type="text"
            className="w-full bg-[#111] border border-gray-800 rounded-md px-4 py-2 text-white"
            placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
            value={regulationId}
            onChange={(e) => setRegulationId(e.target.value)}
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">System Payload (JSON)</label>
          <textarea
            className="w-full bg-[#111] border border-gray-800 rounded-md px-4 py-4 text-white font-mono h-64"
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
          />
        </div>
        
        <button
          onClick={handleCheck}
          disabled={loading || !regulationId}
          className="bg-white text-black px-6 py-2 rounded-md font-medium disabled:opacity-50"
        >
          {loading ? 'Evaluating...' : 'Run Compliance Check'}
        </button>
        
        {error && (
          <div className="bg-red-900/20 border border-red-900/50 text-red-400 p-4 rounded-md">
            {error}
          </div>
        )}
        
        {results && (
          <div className="mt-8">
            <h2 className="text-xl font-semibold mb-4 text-white">Results</h2>
            <div className="bg-[#111] border border-gray-800 rounded-md p-6">
              {results.job_id ? (
                <div>
                  <p className="text-yellow-500 font-medium">Async Job Queued</p>
                  <p className="text-gray-400 mt-2">Job ID: {results.job_id}</p>
                </div>
              ) : (
                <div>
                  <div className="flex items-center space-x-3 mb-6">
                    <span className="text-gray-400">Status:</span>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                      results.status === 'pass' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                    }`}>
                      {results.status.toUpperCase()}
                    </span>
                  </div>
                  
                  {results.violations && results.violations.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-400 mb-3">Violations</h3>
                      <ul className="space-y-3">
                        {results.violations.map((v: any, i: number) => (
                          <li key={i} className="bg-red-900/10 border border-red-900/30 rounded p-3 text-red-300">
                            <strong>{v.rule}:</strong> {v.reason}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
