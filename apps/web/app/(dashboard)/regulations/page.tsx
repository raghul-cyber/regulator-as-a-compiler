"use client";

import { useState } from "react";
import { Upload, FileText, Search, Filter } from "lucide-react";
import UploadModal from "./UploadModal";
import Link from "next/link";

export default function RegulationsPage() {
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  // In a real app, this would be fetched from the backend.
  // For Phase 3, we just have the upload button and an empty state, 
  // or a mock list.
  const regulations: any[] = [];

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Regulations</h1>
          <p className="text-gray-500 mt-1">Manage and track your compliance regulations.</p>
        </div>
        <button
          onClick={() => setIsUploadModalOpen(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors shadow-sm"
        >
          <Upload size={18} />
          Upload Regulation
        </button>
      </div>

      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 flex justify-between items-center">
        <div className="relative w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
          <input
            type="text"
            placeholder="Search regulations..."
            className="w-full pl-10 pr-4 py-2 bg-gray-50 border-none rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
          />
        </div>
        <button className="text-gray-600 hover:text-gray-900 flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors">
          <Filter size={18} />
          Filter
        </button>
      </div>

      {regulations.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-xl p-12 text-center shadow-sm">
          <div className="mx-auto w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center mb-4">
            <FileText className="text-indigo-500" size={32} />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-1">No regulations found</h3>
          <p className="text-gray-500 mb-6 max-w-sm mx-auto">
            Upload your first regulation document (PDF or HTML) to start tracking compliance.
          </p>
          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="bg-white hover:bg-gray-50 text-indigo-600 border border-indigo-200 px-4 py-2 rounded-lg font-medium transition-colors"
          >
            Upload Document
          </button>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          {/* Table would go here */}
        </div>
      )}

      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
      />
    </div>
  );
}
