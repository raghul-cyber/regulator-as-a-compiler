import { UserButton } from "@clerk/nextjs";

export default function DashboardPage() {
  return (
    <div className="p-8">
      <header className="flex justify-between items-center mb-8">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <UserButton afterSignOutUrl="/" />
      </header>
      <main>
        <p>Welcome to Regulation-as-Code Compiler.</p>
      </main>
    </div>
  );
}
