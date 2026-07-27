"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { ArrowLeft, Loader2, PlusCircle, MinusCircle, FileEdit } from "lucide-react";
import Link from "next/link";
import { RequirementCard } from "@/components/requirements/RequirementCard";

export default function DiffViewer() {
  const params = useParams();
  const id = params.id as string;
  const { getToken } = useAuth();
  
  const [diffData, setDiffData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDiff = async () => {
      try {
        const token = await getToken();
        const res = await fetch(`http://localhost:8000/api/regulations/${id}/diff`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        if (!res.ok) {
          throw new Error("Failed to fetch diff");
        }

        const data = await res.json();
        setDiffData(data);
      } catch (err: any) {
        setError(err.message || "An error occurred");
      } finally {
        setLoading(false);
      }
    };

    fetchDiff();
  }, [id, getToken]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-12">
        <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
      </div>
    );
  }

  if (error || !diffData) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <Link href={`/regulations/${id}`} className="flex items-center text-sm text-gray-500 hover:text-gray-900 mb-6">
          <ArrowLeft size={16} className="mr-1" /> Back to regulation
        </Link>
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">
          {error || "Diff not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <Link href={`/regulations/${id}`} className="flex items-center text-sm text-gray-500 hover:text-gray-900 mb-2 w-max transition-colors">
        <ArrowLeft size={16} className="mr-1" /> Back to regulation
      </Link>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-6 border-b border-gray-100 flex justify-between items-start bg-slate-50">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              Semantic Version Diff
            </h1>
            <p className="text-sm text-gray-500 mt-1">Showing changes between the previous version and the current version.</p>
          </div>
          <div className="flex gap-4">
            <div className="flex flex-col items-center p-3 bg-green-50 rounded-lg border border-green-100">
              <span className="text-xl font-bold text-green-600">{diffData.added.length}</span>
              <span className="text-xs text-green-700 font-medium">Added</span>
            </div>
            <div className="flex flex-col items-center p-3 bg-red-50 rounded-lg border border-red-100">
              <span className="text-xl font-bold text-red-600">{diffData.removed.length}</span>
              <span className="text-xs text-red-700 font-medium">Removed</span>
            </div>
            <div className="flex flex-col items-center p-3 bg-blue-50 rounded-lg border border-blue-100">
              <span className="text-xl font-bold text-blue-600">{diffData.modified.length}</span>
              <span className="text-xs text-blue-700 font-medium">Modified</span>
            </div>
          </div>
        </div>

        <div className="p-6 space-y-8 bg-slate-50/50">
          
          {diffData.added.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <PlusCircle className="text-green-500" size={20} />
                Added Requirements
              </h2>
              <div className="space-y-4">
                {diffData.added.map((req: any) => (
                  <div key={req.id} className="border-l-4 border-green-400 bg-white rounded-r-lg shadow-sm">
                    <RequirementCard requirement={req} />
                  </div>
                ))}
              </div>
            </section>
          )}

          {diffData.removed.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <MinusCircle className="text-red-500" size={20} />
                Removed Requirements
              </h2>
              <div className="space-y-4">
                {diffData.removed.map((req: any) => (
                  <div key={req.id} className="border-l-4 border-red-400 opacity-60 bg-white rounded-r-lg shadow-sm">
                    <RequirementCard requirement={req} />
                  </div>
                ))}
              </div>
            </section>
          )}

          {diffData.modified.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <FileEdit className="text-blue-500" size={20} />
                Modified Requirements
              </h2>
              <div className="space-y-6">
                {diffData.modified.map((mod: any, idx: number) => {
                  const { old, new: newReq } = mod;
                  
                  // Compute simple field diffs
                  const changes = [];
                  if (old.severity !== newReq.severity) changes.push(`Severity: ${old.severity} ➔ ${newReq.severity}`);
                  if (old.type !== newReq.type) changes.push(`Type: ${old.type} ➔ ${newReq.type}`);
                  if (old.title !== newReq.title) changes.push(`Title changed`);
                  if (old.description !== newReq.description) changes.push(`Description changed`);

                  return (
                    <div key={idx} className="border border-blue-200 bg-white rounded-lg shadow-sm overflow-hidden">
                      <div className="bg-blue-50 px-4 py-2 border-b border-blue-100 flex justify-between items-center">
                        <span className="text-sm font-semibold text-blue-800">Modification Detected</span>
                        <div className="flex gap-2 text-xs">
                          {changes.map((change, i) => (
                            <span key={i} className="bg-blue-100 text-blue-700 px-2 py-1 rounded-md">{change}</span>
                          ))}
                        </div>
                      </div>
                      <div className="grid grid-cols-2 divide-x divide-gray-200">
                        <div className="p-4 bg-gray-50/50">
                          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Previous Version</h4>
                          <RequirementCard requirement={old} />
                        </div>
                        <div className="p-4">
                          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 text-blue-600">New Version</h4>
                          <RequirementCard requirement={newReq} />
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          {diffData.added.length === 0 && diffData.removed.length === 0 && diffData.modified.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No semantic differences were detected between the versions.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
