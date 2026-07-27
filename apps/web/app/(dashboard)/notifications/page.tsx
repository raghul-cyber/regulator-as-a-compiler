"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Loader2, Bell, AlertTriangle, Info } from "lucide-react";

export default function NotificationsPage() {
  const { getToken } = useAuth();
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNotifications = async () => {
    try {
      const token = await getToken();
      const res = await fetch(`http://localhost:8000/api/v1/notifications`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Failed to fetch notifications");
      const data = await res.json();
      setNotifications(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, [getToken]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-12">
        <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      <div className="flex justify-between items-center border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Notifications</h1>
          <p className="text-gray-500 mt-1">Updates, alerts, and system impacts.</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">
          {error}
        </div>
      )}

      <div className="space-y-4">
        {notifications.map(notif => {
          const isImpactAlert = notif.type === "impact_alert";
          
          return (
            <div key={notif.id} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex gap-4">
              <div className={`mt-1 flex-shrink-0 ${isImpactAlert ? 'text-orange-500' : 'text-blue-500'}`}>
                {isImpactAlert ? <AlertTriangle size={24} /> : <Info size={24} />}
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-900">
                  {isImpactAlert ? "System Impact Alert" : "System Notification"}
                </h3>
                <p className="text-gray-600 mt-1 text-sm">
                  {isImpactAlert 
                    ? `Regulatory changes have impacted the system "${notif.payload.system_name}". Please review the updated requirements.`
                    : "You have a new notification."
                  }
                </p>
                {isImpactAlert && (
                  <div className="mt-3 flex gap-2">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 border border-gray-300">
                      Severity: {notif.payload.severity?.toUpperCase() || "UNKNOWN"}
                    </span>
                    <button className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
                      View details &rarr;
                    </button>
                  </div>
                )}
                <p className="text-xs text-gray-400 mt-4">
                  {new Date(notif.created_at).toLocaleString()}
                </p>
              </div>
            </div>
          );
        })}

        {notifications.length === 0 && !error && (
          <div className="py-12 text-center bg-gray-50 rounded-xl border border-dashed border-gray-300 text-gray-500">
            <Bell className="mx-auto h-12 w-12 text-gray-400 mb-3" />
            No new notifications. You're all caught up!
          </div>
        )}
      </div>
    </div>
  );
}
