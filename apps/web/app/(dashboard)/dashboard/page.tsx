"use client";

import { useEffect, useState } from "react";
import { UserButton, useAuth } from "@clerk/nextjs";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer 
} from "recharts";
import { Activity, ShieldAlert, FileText, CheckCircle } from "lucide-react";
import Link from "next/link";

type Severity = "low" | "medium" | "high" | "critical";
type ValidationStatus = "draft" | "pending_review" | "approved" | "enforceable";

interface DashboardSummary {
  total_requirements: number;
  counts_by_type: Record<string, number>;
  counts_by_severity: Record<string, number>;
  counts_by_status: Record<string, number>;
  recent_activity: {
    id: string;
    action: string;
    title: string;
    created_at: string;
  }[];
  high_risk_controls: {
    id: string;
    title: string;
    severity: Severity;
    validation_status: ValidationStatus;
    regulation_name: string;
  }[];
  affected_systems: {
    id: string;
    system_name: string;
    impact_record_id: string;
    severity: Severity;
    created_at: string;
    status: string;
  }[];
}

export default function DashboardPage() {
  const { getToken, has } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isAuditor = has({ role: "org:auditor" });

  useEffect(() => {
    async function fetchSummary() {
      try {
        const token = await getToken();
        const res = await fetch("http://localhost:8000/api/v1/dashboard/summary", {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        if (!res.ok) throw new Error("Failed to fetch dashboard summary");
        const data = await res.json();
        setSummary(data);
      } catch (e: any) {
        setError(e.message);
      }
    }
    fetchSummary();
  }, [getToken]);

  if (error) {
    return <div className="p-8 text-red-500">Error: {error}</div>;
  }

  if (!summary) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-black text-white">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-4 border-gray-600 border-t-white rounded-full animate-spin" />
          <span className="text-gray-400 font-mono text-sm uppercase tracking-widest">Loading Analytics</span>
        </div>
      </div>
    );
  }

  const chartData = [
    { name: "Low", value: summary.counts_by_severity["low"] || 0, fill: "#3b82f6" },
    { name: "Medium", value: summary.counts_by_severity["medium"] || 0, fill: "#f59e0b" },
    { name: "High", value: summary.counts_by_severity["high"] || 0, fill: "#ef4444" },
    { name: "Critical", value: summary.counts_by_severity["critical"] || 0, fill: "#7f1d1d" },
  ];

  return (
    <div className="min-h-screen bg-black text-gray-100 font-sans selection:bg-gray-800">
      <header className="sticky top-0 z-50 flex items-center justify-between px-8 py-4 bg-black/80 backdrop-blur-md border-b border-gray-800">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 bg-white rounded flex items-center justify-center">
            <span className="text-black font-bold text-xl">R</span>
          </div>
          <h1 className="text-xl font-semibold tracking-tight">Analytics Overview</h1>
        </div>
        <div className="flex items-center gap-4">
          {isAuditor && (
            <span className="px-3 py-1 bg-gray-900 border border-gray-800 text-gray-400 text-xs font-mono rounded-full">
              READ ONLY
            </span>
          )}
          <UserButton afterSignOutUrl="/" appearance={{ elements: { userButtonAvatarBox: "w-8 h-8 border border-gray-800" } }} />
        </div>
      </header>

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        
        {/* Stat Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="Total Requirements" value={summary.total_requirements} icon={<FileText className="w-4 h-4 text-gray-400" />} />
          <StatCard title="Obligations" value={summary.counts_by_type["obligation"] || 0} icon={<CheckCircle className="w-4 h-4 text-green-500" />} />
          <StatCard title="Pending Review" value={summary.counts_by_status["pending_review"] || 0} icon={<Activity className="w-4 h-4 text-yellow-500" />} />
          <StatCard title="Critical Risks" value={summary.counts_by_severity["critical"] || 0} icon={<ShieldAlert className="w-4 h-4 text-red-500" />} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Main Chart */}
          <div className="lg:col-span-2 space-y-4">
            <div className="p-6 bg-[#0a0a0a] border border-gray-800 rounded-xl shadow-2xl">
              <h2 className="text-sm font-mono text-gray-400 uppercase tracking-widest mb-6">Severity Distribution</h2>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                    <XAxis dataKey="name" stroke="#6b7280" tickLine={false} axisLine={false} />
                    <YAxis stroke="#6b7280" tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip 
                      cursor={{fill: '#1f2937'}} 
                      contentStyle={{ backgroundColor: '#000', borderColor: '#374151', borderRadius: '8px' }}
                      itemStyle={{ color: '#fff' }}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={60} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* High-Risk Controls Table */}
            <div className="p-6 bg-[#0a0a0a] border border-gray-800 rounded-xl shadow-2xl overflow-hidden">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-sm font-mono text-red-400 uppercase tracking-widest flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4" /> High-Risk Controls
                </h2>
              </div>
              
              {summary.high_risk_controls.length === 0 ? (
                <div className="py-12 text-center text-gray-500 font-mono text-sm">
                  No high-risk controls pending approval.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-gray-800 text-xs font-mono text-gray-500">
                        <th className="py-3 px-4 font-normal">Requirement</th>
                        <th className="py-3 px-4 font-normal">Regulation</th>
                        <th className="py-3 px-4 font-normal">Severity</th>
                        <th className="py-3 px-4 font-normal">Status</th>
                        <th className="py-3 px-4 font-normal text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.high_risk_controls.map((control) => (
                        <tr key={control.id} className="border-b border-gray-800/50 hover:bg-gray-900/30 transition-colors group">
                          <td className="py-4 px-4">
                            <p className="text-sm font-medium text-gray-200 line-clamp-1">{control.title}</p>
                            <p className="text-xs text-gray-500 font-mono mt-1">{control.id.split('-')[0]}</p>
                          </td>
                          <td className="py-4 px-4 text-sm text-gray-400">{control.regulation_name}</td>
                          <td className="py-4 px-4">
                            <SeverityBadge severity={control.severity} />
                          </td>
                          <td className="py-4 px-4">
                            <StatusBadge status={control.validation_status} />
                          </td>
                          <td className="py-4 px-4 text-right">
                            <Link 
                              href={`/regulations/${control.id}`} 
                              className="text-xs font-mono text-blue-400 hover:text-blue-300 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              Review &rarr;
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Affected Systems Table */}
            <div className="p-6 bg-[#0a0a0a] border border-gray-800 rounded-xl shadow-2xl overflow-hidden mt-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-sm font-mono text-orange-400 uppercase tracking-widest flex items-center gap-2">
                  <Activity className="w-4 h-4" /> Affected Systems
                </h2>
              </div>
              
              {(!summary.affected_systems || summary.affected_systems.length === 0) ? (
                <div className="py-12 text-center text-gray-500 font-mono text-sm">
                  No systems currently impacted by regulatory changes.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-gray-800 text-xs font-mono text-gray-500">
                        <th className="py-3 px-4 font-normal">System</th>
                        <th className="py-3 px-4 font-normal">Impact Severity</th>
                        <th className="py-3 px-4 font-normal">Date Logged</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.affected_systems.map((sys) => (
                        <tr key={sys.impact_record_id} className="border-b border-gray-800/50 hover:bg-gray-900/30 transition-colors">
                          <td className="py-4 px-4 text-sm font-medium text-gray-200">
                            {sys.system_name}
                          </td>
                          <td className="py-4 px-4">
                            <SeverityBadge severity={sys.severity} />
                          </td>
                          <td className="py-4 px-4 text-xs text-gray-500 font-mono">
                            {new Date(sys.created_at).toLocaleDateString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* Recent Activity Feed */}
          <div className="space-y-4">
            <div className="p-6 bg-[#0a0a0a] border border-gray-800 rounded-xl shadow-2xl h-full">
              <h2 className="text-sm font-mono text-gray-400 uppercase tracking-widest mb-6">Activity Feed</h2>
              <div className="space-y-6">
                {summary.recent_activity.length === 0 ? (
                  <p className="text-sm text-gray-500 font-mono">No recent activity.</p>
                ) : (
                  summary.recent_activity.map((activity, idx) => (
                    <div key={activity.id} className="relative pl-6">
                      {idx !== summary.recent_activity.length - 1 && (
                        <div className="absolute top-6 left-2 bottom-[-24px] w-px bg-gray-800" />
                      )}
                      <div className="absolute top-1.5 left-1 w-2.5 h-2.5 rounded-full bg-gray-700 ring-4 ring-[#0a0a0a]" />
                      <p className="text-sm text-gray-300">
                        <span className="font-medium text-white">{formatAction(activity.action)}</span>
                        {" · "}
                        <span className="text-gray-500 truncate" title={activity.title}>
                          {activity.title.substring(0, 30)}{activity.title.length > 30 ? "..." : ""}
                        </span>
                      </p>
                      <p className="text-xs text-gray-500 font-mono mt-1">
                        {new Date(activity.created_at).toLocaleString()}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}

function StatCard({ title, value, icon }: { title: string, value: number, icon: React.ReactNode }) {
  return (
    <div className="p-6 bg-[#0a0a0a] border border-gray-800 rounded-xl shadow-2xl flex flex-col justify-between">
      <div className="flex justify-between items-start">
        <h3 className="text-gray-400 text-sm font-medium">{title}</h3>
        {icon}
      </div>
      <div className="mt-4 flex items-baseline">
        <span className="text-3xl font-bold text-white tracking-tight">{value}</span>
      </div>
    </div>
  );
}

function SeverityBadge({ severity }: { severity: Severity }) {
  const styles = {
    low: "bg-blue-900/30 text-blue-400 border-blue-800",
    medium: "bg-yellow-900/30 text-yellow-400 border-yellow-800",
    high: "bg-red-900/30 text-red-400 border-red-800",
    critical: "bg-red-900/50 text-red-300 border-red-700 animate-pulse",
  };
  return (
    <span className={`px-2 py-1 text-xs font-mono border rounded ${styles[severity] || styles.low}`}>
      {severity.toUpperCase()}
    </span>
  );
}

function StatusBadge({ status }: { status: ValidationStatus }) {
  const styles = {
    draft: "bg-gray-800 text-gray-400",
    pending_review: "bg-yellow-900/30 text-yellow-400 border border-yellow-800/50",
    approved: "bg-green-900/30 text-green-400 border border-green-800/50",
    enforceable: "bg-blue-900/30 text-blue-400 border border-blue-800/50",
  };
  const label = status.replace("_", " ").toUpperCase();
  return (
    <span className={`px-2 py-1 text-xs font-mono rounded ${styles[status] || styles.draft}`}>
      {label}
    </span>
  );
}

function formatAction(action: string) {
  if (action === "requirement.status_changed") return "Status Changed";
  if (action === "requirement.created") return "Extracted";
  if (action === "regulation.uploaded") return "Regulation Uploaded";
  return action;
}
