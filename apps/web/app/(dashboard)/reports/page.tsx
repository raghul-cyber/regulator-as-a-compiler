"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { Download, FileText, Loader2, Plus } from "lucide-react";
import { CompilationMesh } from "@/components/ui/compilation-mesh";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Regulation = { id: string; name: string; jurisdiction: string };
type Report = { id: string; regulation_id: string; report_type: string; generated_at: string; download_url: string };

export default function ReportsLibraryPage() {
  const { getToken } = useAuth();
  const [regulations, setRegulations] = useState<Regulation[]>([]);
  const [selectedReg, setSelectedReg] = useState<string>("");
  const [reports, setReports] = useState<Report[]>([]);
  
  const [isGenerating, setIsGenerating] = useState(false);
  const [reportTypeToGen, setReportTypeToGen] = useState<string>("executive_summary");

  useEffect(() => {
    async function fetchRegs() {
      const token = await getToken();
      const res = await fetch("http://localhost:8000/api/v1/regulations", {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setRegulations(data);
        if (data.length > 0) {
          setSelectedReg(data[0].id);
        }
      }
    }
    fetchRegs();
  }, [getToken]);

  useEffect(() => {
    async function fetchReports() {
      if (!selectedReg) return;
      const token = await getToken();
      const res = await fetch(`http://localhost:8000/api/v1/reports/${selectedReg}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setReports(await res.json());
      }
    }
    fetchReports();
  }, [selectedReg, getToken]);

  const handleGenerate = async () => {
    if (!selectedReg) return;
    setIsGenerating(true);
    
    // Artificial delay to show off the R3F compilation mesh
    await new Promise(resolve => setTimeout(resolve, 3000));

    try {
      const token = await getToken();
      const res = await fetch("http://localhost:8000/api/v1/reports", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ regulation_id: selectedReg, report_type: reportTypeToGen })
      });
      
      if (res.ok) {
        const newReport = await res.json();
        setReports(prev => [...prev, newReport]);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8 text-gray-200">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-mono tracking-tight text-white mb-2">Reports Library</h1>
          <p className="text-sm text-gray-400">Generate deterministic compliance reports.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
        <div className="col-span-1 border border-gray-800 rounded-lg p-4 bg-[#0a0a0a]">
          <h2 className="text-sm font-semibold mb-4 text-gray-400 uppercase tracking-wider">Regulations</h2>
          <div className="space-y-2">
            {regulations.map(reg => (
              <button
                key={reg.id}
                onClick={() => setSelectedReg(reg.id)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${selectedReg === reg.id ? 'bg-gray-800 text-white' : 'hover:bg-gray-800/50 text-gray-400'}`}
              >
                {reg.name}
              </button>
            ))}
          </div>
        </div>

        <div className="col-span-3 space-y-6">
          <div className="flex items-center justify-between bg-[#0a0a0a] p-4 border border-gray-800 rounded-lg">
            <div className="flex items-center gap-4">
              <Select value={reportTypeToGen} onValueChange={setReportTypeToGen}>
                <SelectTrigger className="w-[200px] bg-black border-gray-800">
                  <SelectValue placeholder="Select report type" />
                </SelectTrigger>
                <SelectContent className="bg-black border-gray-800 text-gray-200">
                  <SelectItem value="executive_summary">Executive Summary</SelectItem>
                  <SelectItem value="technical">Technical Details</SelectItem>
                  <SelectItem value="audit_evidence">Audit Evidence</SelectItem>
                  <SelectItem value="gap_analysis">Gap Analysis</SelectItem>
                  <SelectItem value="checklist">Compliance Checklist</SelectItem>
                </SelectContent>
              </Select>
              <Button onClick={handleGenerate} disabled={isGenerating || !selectedReg} className="bg-white text-black hover:bg-gray-200">
                {isGenerating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
                Generate Report
              </Button>
            </div>
          </div>

          {isGenerating ? (
            <div className="border border-gray-800 rounded-lg overflow-hidden bg-black">
              <CompilationMesh />
            </div>
          ) : (
            <div className="bg-[#0a0a0a] border border-gray-800 rounded-lg overflow-hidden">
              <table className="w-full text-sm text-left">
                <thead className="bg-[#111] text-gray-400 border-b border-gray-800 font-mono text-xs uppercase">
                  <tr>
                    <th className="px-6 py-4">Report Type</th>
                    <th className="px-6 py-4">Generated At</th>
                    <th className="px-6 py-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {reports.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-6 py-8 text-center text-gray-500">No reports generated yet.</td>
                    </tr>
                  ) : (
                    reports.map(r => (
                      <tr key={r.id} className="hover:bg-[#111] transition-colors">
                        <td className="px-6 py-4 font-medium text-gray-200">
                          {r.report_type.replace('_', ' ').toUpperCase()}
                        </td>
                        <td className="px-6 py-4 text-gray-400">
                          {new Date(r.generated_at).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <a href={`http://localhost:8000${r.download_url}`} className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 border border-gray-800 bg-transparent hover:bg-gray-800 h-9 px-4 py-2 text-white">
                            <Download className="w-4 h-4 mr-2" />
                            Download PDF
                          </a>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
