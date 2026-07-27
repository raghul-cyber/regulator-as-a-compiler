"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { RefreshCw, AlertTriangle, CheckCircle, Clock } from "lucide-react";

interface Job {
  id: string;
  job_type: string;
  status: string;
  payload: any;
  error_message: string | null;
  retries: number;
  created_at: string;
  updated_at: string;
}

export default function JobsAdminPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [requeuing, setRequeuing] = useState<string | null>(null);
  const { getToken } = useAuth();

  const fetchJobs = async () => {
    try {
      const token = await getToken();
      const res = await fetch("http://localhost:8000/api/v1/jobs", {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setJobs(await res.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleRequeue = async (jobId: string) => {
    setRequeuing(jobId);
    try {
      const token = await getToken();
      const res = await fetch(`http://localhost:8000/api/v1/jobs/${jobId}/requeue`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        await fetchJobs();
      } else {
        alert("Failed to requeue job");
      }
    } catch (e) {
      console.error(e);
      alert("Error requeuing job");
    } finally {
      setRequeuing(null);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-gray-400">Loading jobs...</div>;
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed": return <CheckCircle className="text-emerald-500 w-5 h-5" />;
      case "dead_letter":
      case "failed": return <AlertTriangle className="text-red-500 w-5 h-5" />;
      default: return <Clock className="text-yellow-500 w-5 h-5" />;
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-end mb-8 border-b border-white/5 pb-4">
        <div>
          <h1 className="text-3xl font-light text-white tracking-tight">Background Jobs</h1>
          <p className="text-gray-400 mt-2 font-light">Monitor system tasks and manage the dead-letter queue.</p>
        </div>
        <button 
          onClick={fetchJobs}
          className="flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] hover:bg-[#252525] border border-white/10 rounded-md text-sm text-gray-300 transition-colors"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="bg-[#111111] border border-white/10 rounded-xl overflow-hidden shadow-2xl">
        <table className="w-full text-sm text-left">
          <thead className="bg-[#161616] border-b border-white/5 text-gray-400 font-medium">
            <tr>
              <th className="px-6 py-4">Status</th>
              <th className="px-6 py-4">Job Type</th>
              <th className="px-6 py-4">Job ID</th>
              <th className="px-6 py-4">Created</th>
              <th className="px-6 py-4">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {jobs.map((job) => (
              <tr key={job.id} className="hover:bg-white/[0.02] transition-colors group">
                <td className="px-6 py-4 flex items-center gap-2">
                  {getStatusIcon(job.status)}
                  <span className="capitalize text-gray-300">{job.status.replace("_", " ")}</span>
                </td>
                <td className="px-6 py-4 text-gray-300 capitalize">{job.job_type}</td>
                <td className="px-6 py-4 font-mono text-xs text-gray-500">
                  {job.id}
                  {job.error_message && (
                    <div className="mt-1 text-red-400/80 line-clamp-1 max-w-xs" title={job.error_message}>
                      {job.error_message}
                    </div>
                  )}
                </td>
                <td className="px-6 py-4 text-gray-400">
                  {new Date(job.created_at).toLocaleString()}
                </td>
                <td className="px-6 py-4">
                  {(job.status === "dead_letter" || job.status === "failed") && (
                    <button
                      onClick={() => handleRequeue(job.id)}
                      disabled={requeuing === job.id}
                      className="text-xs bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 px-3 py-1.5 rounded transition-colors disabled:opacity-50 border border-indigo-500/20"
                    >
                      {requeuing === job.id ? "Requeuing..." : "Requeue Job"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                  No background jobs found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
