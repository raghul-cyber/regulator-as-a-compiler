"use client";

import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Search, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { useAuth } from "@clerk/nextjs";

export type Requirement = {
  id: string;
  regulation_version_id: string;
  section_id: string | null;
  type: string;
  title: string;
  description: string;
  conditions: { items: string[] };
  actions: { items: string[] };
  severity: string;
  evidence_required: { items: string[] };
  references: { items: string[] };
  confidence_score: number;
  validation_status: string;
  rejection_reason?: string;
  reviewed_by_user_id?: string;
  reviewed_at?: string;
};

interface RequirementBrowserProps {
  regulationId: string;
  isReviewQueue?: boolean;
}

export function RequirementBrowser({ regulationId, isReviewQueue = false }: RequirementBrowserProps) {
  const { getToken } = useAuth();
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState(isReviewQueue ? "pending_review" : "");
  
  // Rejection State
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");

  const fetchRequirements = async () => {
    try {
      setLoading(true);
      const token = await getToken();
      
      const query = new URLSearchParams();
      if (search) query.append("search", search);
      if (type) query.append("type", type);
      if (severity) query.append("severity", severity);
      if (status) query.append("status", status);
      
      const res = await fetch(`http://localhost:8000/api/regulations/${regulationId}/requirements?${query.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      
      if (res.ok) {
        const data = await res.json();
        setRequirements(data.items);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequirements();
  }, [search, type, severity, status, regulationId]);

  const updateStatus = async (id: string, newStatus: string, reason?: string) => {
    try {
      const token = await getToken();
      const payload: any = { validation_status: newStatus };
      if (reason) payload.rejection_reason = reason;

      const res = await fetch(`http://localhost:8000/api/requirements/${id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        fetchRequirements();
      } else {
        const err = await res.json();
        alert(`Error: ${err.detail}`);
      }
    } catch (e) {
      console.error(e);
      alert("An unexpected error occurred.");
    }
  };

  const severityColor = (sev: string) => {
    switch (sev) {
      case "critical": return "bg-red-500/10 text-red-600 border-red-500/20";
      case "high": return "bg-orange-500/10 text-orange-600 border-orange-500/20";
      case "medium": return "bg-yellow-500/10 text-yellow-600 border-yellow-500/20";
      case "low": return "bg-green-500/10 text-green-600 border-green-500/20";
      default: return "bg-gray-100 text-gray-600";
    }
  };

  const statusColor = (st: string) => {
    switch (st) {
      case "enforceable": return "bg-emerald-500/10 text-emerald-600";
      case "approved": return "bg-blue-500/10 text-blue-600";
      case "pending_review": return "bg-purple-500/10 text-purple-600";
      case "draft": return "bg-slate-500/10 text-slate-600";
      default: return "bg-gray-100 text-gray-600";
    }
  };

  return (
    <div className="w-full space-y-6">
      {/* Controls */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between bg-white p-4 rounded-xl shadow-sm border border-slate-100">
        <div className="relative w-full md:w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input 
            type="text" 
            placeholder="Search requirements..." 
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        
        <div className="flex gap-3 w-full md:w-auto overflow-x-auto">
          <select 
            className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm outline-none"
            value={type} onChange={(e) => setType(e.target.value)}
          >
            <option value="">All Types</option>
            <option value="obligation">Obligation</option>
            <option value="prohibition">Prohibition</option>
            <option value="permission">Permission</option>
          </select>

          <select 
            className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm outline-none"
            value={severity} onChange={(e) => setSeverity(e.target.value)}
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          {!isReviewQueue && (
            <select 
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm outline-none"
              value={status} onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="pending_review">Pending Review</option>
              <option value="approved">Approved</option>
              <option value="enforceable">Enforceable</option>
            </select>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 border-b border-slate-200 text-slate-500 text-xs font-semibold uppercase tracking-wider">
                <th className="w-10 px-4 py-3"></th>
                <th className="px-4 py-3">Requirement</th>
                <th className="px-4 py-3 w-32">Type</th>
                <th className="px-4 py-3 w-32">Severity</th>
                <th className="px-4 py-3 w-40">Status</th>
                {isReviewQueue && <th className="px-4 py-3 w-48 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Loading requirements...</td></tr>
              ) : requirements.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">No requirements found matching criteria.</td></tr>
              ) : (
                requirements.map((req) => (
                  <React.Fragment key={req.id}>
                    <tr 
                      className={`hover:bg-slate-50/50 transition-colors ${expandedId === req.id ? 'bg-slate-50' : ''}`}
                    >
                      <td className="px-4 py-4">
                        <button 
                          onClick={() => setExpandedId(expandedId === req.id ? null : req.id)}
                          className="p-1 hover:bg-slate-200 rounded-md transition-colors text-slate-400"
                        >
                          {expandedId === req.id ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                        </button>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-start gap-2">
                          <div className="font-medium text-slate-900 line-clamp-2">
                            {req.title}
                          </div>
                          {req.confidence_score < 0.8 && (
                            <div title="Low confidence extraction" className="mt-0.5 text-amber-500">
                              <AlertTriangle size={14} />
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <span className="capitalize text-sm text-slate-600">{req.type}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${severityColor(req.severity)}`}>
                          {req.severity}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${statusColor(req.validation_status)}`}>
                          {req.validation_status.replace('_', ' ')}
                        </span>
                      </td>
                      {isReviewQueue && (
                        <td className="px-4 py-4 text-right">
                          {rejectingId === req.id ? (
                            <div className="flex flex-col gap-2 items-end">
                              <input 
                                type="text" 
                                placeholder="Reason for rejection..." 
                                className="w-full px-2 py-1 text-sm border rounded"
                                value={rejectionReason}
                                onChange={e => setRejectionReason(e.target.value)}
                              />
                              <div className="flex gap-2">
                                <button onClick={() => setRejectingId(null)} className="text-xs text-slate-500 hover:underline">Cancel</button>
                                <button 
                                  onClick={() => {
                                    updateStatus(req.id, "draft", rejectionReason);
                                    setRejectingId(null);
                                    setRejectionReason("");
                                  }} 
                                  className="text-xs bg-red-500 text-white px-2 py-1 rounded"
                                >
                                  Confirm Reject
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex justify-end gap-2">
                              <button 
                                onClick={() => updateStatus(req.id, "approved")}
                                className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded-md transition-colors"
                                title="Approve"
                              >
                                <CheckCircle size={18} />
                              </button>
                              <button 
                                onClick={() => setRejectingId(req.id)}
                                className="p-1.5 text-red-600 hover:bg-red-50 rounded-md transition-colors"
                                title="Reject"
                              >
                                <XCircle size={18} />
                              </button>
                            </div>
                          )}
                        </td>
                      )}
                    </tr>
                    
                    {/* Expanded Details Row */}
                    {expandedId === req.id && (
                      <tr>
                        <td colSpan={isReviewQueue ? 6 : 5} className="p-0 border-b border-slate-200">
                          <div className="p-6 bg-slate-50/50 border-t border-slate-100 shadow-inner">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                              <div className="space-y-6">
                                <div>
                                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Description</h4>
                                  <p className="text-sm text-slate-700 leading-relaxed">{req.description}</p>
                                </div>
                                
                                {req.conditions?.items?.length > 0 && (
                                  <div>
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Conditions</h4>
                                    <ul className="list-disc list-inside text-sm text-slate-700 space-y-1">
                                      {req.conditions.items.map((cond, i) => <li key={i}>{cond}</li>)}
                                    </ul>
                                  </div>
                                )}
                              </div>
                              
                              <div className="space-y-6">
                                {req.actions?.items?.length > 0 && (
                                  <div>
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Required Actions</h4>
                                    <ul className="list-disc list-inside text-sm text-slate-700 space-y-1">
                                      {req.actions.items.map((act, i) => <li key={i}>{act}</li>)}
                                    </ul>
                                  </div>
                                )}
                                
                                {req.evidence_required?.items?.length > 0 && (
                                  <div>
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Evidence Required</h4>
                                    <ul className="list-disc list-inside text-sm text-slate-700 space-y-1">
                                      {req.evidence_required.items.map((ev, i) => <li key={i}>{ev}</li>)}
                                    </ul>
                                  </div>
                                )}
                                
                                {req.references?.items?.length > 0 && (
                                  <div>
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Source Traceability</h4>
                                    <div className="flex flex-wrap gap-2">
                                      {req.references.items.map((ref, i) => (
                                        <a 
                                          key={i} 
                                          href={`/regulations/${regulationId}/document#${ref.replace(/\s+/g, '-').toLowerCase()}`}
                                          className="px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-md hover:bg-blue-100 transition-colors"
                                        >
                                          {ref}
                                        </a>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                {req.rejection_reason && (
                                  <div className="p-3 bg-red-50 border border-red-100 rounded-lg">
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-red-600 mb-1">Rejection Reason</h4>
                                    <p className="text-sm text-red-800">{req.rejection_reason}</p>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
