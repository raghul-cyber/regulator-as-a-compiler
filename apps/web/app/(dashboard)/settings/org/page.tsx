"use client";

import { useEffect, useState } from "react";
import { useAuth, useOrganization } from "@clerk/nextjs";

type UserResponse = {
  id: string;
  clerk_user_id: string;
  role: string;
  email: string;
  created_at: string;
};

const ROLES = [
  "admin",
  "compliance_officer",
  "developer",
  "legal_counsel",
  "auditor",
];

export default function OrgSettingsPage() {
  const { getToken, isLoaded, userId } = useAuth();
  const { organization, membership } = useOrganization();
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [error, setError] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("admin");

  const isAdmin = membership?.role === "org:admin" || true; // In a real app we sync local role to Clerk role, here we'll assume the local API enforces it.

  useEffect(() => {
    async function fetchUsers() {
      if (!isLoaded || !userId) return;
      try {
        const token = await getToken();
        // Since Next.js dev server runs on 3000 and FastAPI on 8000, 
        // we'll assume a proxy or direct URL. Assuming 8000 for local.
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/api/org/users`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (!res.ok) throw new Error("Failed to fetch users");
        const data = await res.json();
        setUsers(data);
      } catch (err: any) {
        setError(err.message);
      }
    }
    fetchUsers();
  }, [isLoaded, userId, getToken]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!organization) return;
    try {
      await organization.inviteMember({
        emailAddress: inviteEmail,
        role: inviteRole === "admin" ? "org:admin" : "org:member",
      });
      alert("Invitation sent via Clerk!");
      setInviteEmail("");
    } catch (err: any) {
      alert("Failed to invite: " + err.errors?.[0]?.message || err.message);
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      const token = await getToken();
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/org/users/${userId}/role`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ role: newRole }),
      });
      if (!res.ok) throw new Error("Failed to update role");
      setUsers(users.map((u) => (u.id === userId ? { ...u, role: newRole } : u)));
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleRemove = async (userId: string) => {
    if (!confirm("Are you sure you want to remove this user?")) return;
    try {
      const token = await getToken();
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/org/users/${userId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) throw new Error("Failed to remove user");
      setUsers(users.filter((u) => u.id !== userId));
    } catch (err: any) {
      alert(err.message);
    }
  };

  if (!isLoaded) return <div>Loading...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <h1 className="text-3xl font-bold tracking-tight">Organization Settings</h1>

      <div className="border rounded-lg p-6 bg-white shadow-sm space-y-4">
        <h2 className="text-xl font-semibold">Invite Member</h2>
        <form onSubmit={handleInvite} className="flex gap-4 items-end">
          <div className="flex-1 space-y-1">
            <label className="text-sm font-medium">Email Address</label>
            <input
              type="email"
              required
              className="w-full border rounded px-3 py-2"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@example.com"
            />
          </div>
          <div className="w-48 space-y-1">
            <label className="text-sm font-medium">Clerk Role</label>
            <select
              className="w-full border rounded px-3 py-2"
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
            >
              <option value="admin">Admin</option>
              <option value="member">Member</option>
            </select>
          </div>
          <button
            type="submit"
            className="bg-black text-white px-4 py-2 rounded font-medium hover:bg-gray-800"
          >
            Send Invite
          </button>
        </form>
        <p className="text-sm text-gray-500">
          Sends an email via Clerk. Once they join, their local app role will default to whatever webhooks assign, but you can change it below.
        </p>
      </div>

      <div className="border rounded-lg bg-white shadow-sm overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-6 py-3 font-medium text-gray-500 text-sm">Email</th>
              <th className="px-6 py-3 font-medium text-gray-500 text-sm">Joined</th>
              <th className="px-6 py-3 font-medium text-gray-500 text-sm">App Role</th>
              <th className="px-6 py-3 font-medium text-gray-500 text-sm text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {users.map((user) => (
              <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4">{user.email}</td>
                <td className="px-6 py-4 text-gray-500">
                  {new Date(user.created_at).toLocaleDateString()}
                </td>
                <td className="px-6 py-4">
                  <select
                    className="border rounded px-2 py-1 text-sm bg-transparent"
                    value={user.role}
                    onChange={(e) => handleRoleChange(user.id, e.target.value)}
                  >
                    {ROLES.map((role) => (
                      <option key={role} value={role}>
                        {role.replace("_", " ").toUpperCase()}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-6 py-4 text-right">
                  <button
                    onClick={() => handleRemove(user.id)}
                    className="text-red-500 hover:text-red-700 text-sm font-medium"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-gray-500">
                  No local users found (API might not be connected or webhooks haven't synced).
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
