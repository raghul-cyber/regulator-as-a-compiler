"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Loader2, Plus, Server, Trash2, Edit } from "lucide-react";

export default function SystemsPage() {
  const { getToken } = useAuth();
  const [systems, setSystems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSystems = async () => {
    try {
      const token = await getToken();
      const res = await fetch(`http://localhost:8000/api/v1/systems`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Failed to fetch systems");
      const data = await res.json();
      setSystems(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSystems();
  }, [getToken]);

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this system mapping?")) return;
    try {
      const token = await getToken();
      const res = await fetch(`http://localhost:8000/api/v1/systems/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Failed to delete system");
      fetchSystems();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleCreateMock = async () => {
    try {
      const token = await getToken();
      const res = await fetch(`http://localhost:8000/api/v1/systems`, {
        method: "POST",
        headers: { 
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          system_name: `System ${Math.floor(Math.random() * 1000)}`,
          mapped_requirement_ids: []
        })
      });
      if (!res.ok) throw new Error("Failed to create system");
      fetchSystems();
    } catch (err: any) {
      alert(err.message);
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-12">
        <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">System Mappings</h1>
          <p className="text-gray-500 mt-1">Map your internal systems to regulatory requirements.</p>
        </div>
        <button 
          onClick={handleCreateMock}
          className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 bg-indigo-600 text-white shadow hover:bg-indigo-700 h-9 px-4 py-2"
        >
          <Plus size={16} className="mr-2" />
          Add System
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {systems.map(sys => (
          <div key={sys.id} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2 text-indigo-600">
                  <Server size={20} />
                  <h3 className="font-semibold text-gray-900">{sys.system_name}</h3>
                </div>
                <div className="flex gap-2">
                  <button className="text-gray-400 hover:text-indigo-600 transition-colors">
                    <Edit size={16} />
                  </button>
                  <button onClick={() => handleDelete(sys.id)} className="text-gray-400 hover:text-red-600 transition-colors">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              <p className="text-sm text-gray-500">
                Mapped to <span className="font-semibold text-gray-700">{sys.mapped_requirement_ids?.length || 0}</span> requirements
              </p>
            </div>
          </div>
        ))}

        {systems.length === 0 && !error && (
          <div className="col-span-full py-12 text-center bg-gray-50 rounded-xl border border-dashed border-gray-300 text-gray-500">
            <Server className="mx-auto h-12 w-12 text-gray-400 mb-3" />
            No system mappings found. Add your first system to start mapping.
          </div>
        )}
      </div>
    </div>
  );
}
