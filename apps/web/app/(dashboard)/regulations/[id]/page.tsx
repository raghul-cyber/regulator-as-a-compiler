"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { FileText, Loader2, ArrowLeft, CheckCircle2 } from "lucide-react";
import Link from "next/link";

export default function RegulationDetail() {
  const params = useParams();
  const id = params.id as string;
  const { getToken } = useAuth();
  
  const [regulation, setRegulation] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
              <span className="bg-yellow-100 text-yellow-800 text-xs font-semibold px-2.5 py-0.5 rounded-full flex items-center gap-1">
                <Loader2 size={12} className="animate-spin" />
                Processing
              </span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <FileText className="text-gray-400" />
              {regulation.name}
            </h1>
          </div>
        </div>

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
            
            <div className="mt-8 space-y-4 text-left bg-white p-4 rounded-lg shadow-sm border border-gray-100">
              <div className="flex items-center gap-3 text-sm text-gray-700">
                <CheckCircle2 className="text-green-500" size={18} />
                <span>Document Uploaded</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-indigo-600 font-medium">
                <Loader2 className="animate-spin" size={18} />
                <span>Extracting requirements and structure</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-gray-400">
                <div className="w-[18px] h-[18px] rounded-full border-2 border-gray-300"></div>
                <span>Generating embeddings</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-gray-400">
                <div className="w-[18px] h-[18px] rounded-full border-2 border-gray-300"></div>
                <span>Finalizing metadata</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
