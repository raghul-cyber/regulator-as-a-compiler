"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { FileText, Loader2, ArrowLeft, CheckCircle2, AlertCircle, Download } from "lucide-react";
import Link from "next/link";
import { RequirementBrowser } from "@/components/requirements/RequirementBrowser";

export default function RegulationDetail() {
  const params = useParams();
  const id = params.id as string;
  const { getToken } = useAuth();
  
  const [regulation, setRegulation] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "review">("overview");

  useEffect(() => {
    const fetchRegulation = async () => {
      try {
        const token = await getToken();
        // Uses rewrite in Next.js
        const res = await fetch(`http://localhost:8000/api/regulations/${id}`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });

        if (!res.ok) {
          throw new Error("Failed to fetch regulation details");
        }

        const data = await res.json();
        setRegulation(data);
      } catch (err: any) {
        setError(err.message || "An error occurred");
      } finally {
        setLoading(false);
      }
    };

    fetchRegulation();
  }, [id, getToken]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-12">
        <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
      </div>
    );
  }

  if (error || !regulation) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <Link href="/regulations" className="flex items-center text-sm text-gray-500 hover:text-gray-900 mb-6">
          <ArrowLeft size={16} className="mr-1" /> Back to regulations
        </Link>
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">
          {error || "Regulation not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <Link href="/regulations" className="flex items-center text-sm text-gray-500 hover:text-gray-900 mb-2 w-max transition-colors">
        <ArrowLeft size={16} className="mr-1" /> Back to regulations
      </Link>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-6 border-b border-gray-100 flex justify-between items-start">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="bg-indigo-100 text-indigo-800 text-xs font-semibold px-2.5 py-0.5 rounded-full">
                {regulation.jurisdiction}
              </span>
              <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full flex items-center gap-1 ${
                regulation.status === 'Processed' ? 'bg-green-100 text-green-800' : 
                regulation.status.includes('Failed') ? 'bg-red-100 text-red-800' :
                'bg-yellow-100 text-yellow-800'
              }`}>
                {regulation.status !== 'Processed' && !regulation.status.includes('Failed') && <Loader2 size={12} className="animate-spin" />}
                {regulation.status === 'Processed' && <CheckCircle2 size={12} />}
                {regulation.status.includes('Failed') && <AlertCircle size={12} />}
                {regulation.status}
              </span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <FileText className="text-gray-400" />
              {regulation.name}
            </h1>
          </div>
          {regulation.status === 'Processed' && (
            <div className="flex gap-2">
              <button 
                onClick={async () => {
                  const token = await getToken();
                  const res = await fetch(`http://localhost:8000/api/v1/regulations/${id}/export`, {
                    headers: { Authorization: `Bearer ${token}` }
                  });
                  if (res.ok) {
                    const blob = await res.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${regulation.name.replace(/\s+/g, '_')}_export.json`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                  }
                }}
                className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 border border-gray-200 bg-white hover:bg-gray-100 hover:text-gray-900 h-9 px-4 py-2"
              >
                <Download className="w-4 h-4 mr-2" />
                Export JSON
              </button>
              <Link 
                href={`/regulations/${id}/diff`}
                className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring border border-gray-200 bg-white hover:bg-gray-100 hover:text-gray-900 h-9 px-4 py-2"
              >
                View Changes
              </Link>
            </div>
          )}
        </div>

        {regulation.status === 'Processed' ? (
          <div>
            <div className="flex border-b border-slate-200">
              <button 
                onClick={() => setActiveTab("overview")}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === "overview" ? "border-indigo-500 text-indigo-600" : "border-transparent text-slate-500 hover:text-slate-700"}`}
              >
                Requirement Browser
              </button>
              <button 
                onClick={() => setActiveTab("review")}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === "review" ? "border-indigo-500 text-indigo-600" : "border-transparent text-slate-500 hover:text-slate-700"}`}
              >
                Review Queue
              </button>
            </div>
            <div className="p-6 bg-slate-50/30">
              {activeTab === "overview" && (
                <RequirementBrowser regulationId={id} isReviewQueue={false} />
              )}
              {activeTab === "review" && (
                <RequirementBrowser regulationId={id} isReviewQueue={true} />
              )}
            </div>
          </div>
        ) : regulation.status.includes('Failed') ? (
          <div className="p-6 bg-gray-50">
            <div className="max-w-md mx-auto text-center py-12">
              <AlertCircle className="mx-auto text-red-500 mb-4" size={48} />
              <h3 className="text-xl font-semibold text-gray-900 mb-2">Processing Failed</h3>
              <p className="text-gray-500">
                The extraction pipeline failed. Please check the logs.
              </p>
            </div>
          </div>
        ) : (
          <div className="p-6 bg-gray-50">
            <div className="max-w-md mx-auto text-center py-12">
              <div className="relative w-24 h-24 mx-auto mb-6">
                <div className="absolute inset-0 border-4 border-indigo-100 rounded-full"></div>
                <div className="absolute inset-0 border-4 border-indigo-500 rounded-full border-t-transparent animate-spin"></div>
                <FileText className="absolute inset-0 m-auto text-indigo-500" size={32} />
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">Analyzing Document...</h3>
              <p className="text-gray-500">
                The AI extraction pipeline is currently processing the regulation document. 
                This may take a few minutes depending on the size of the file.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
