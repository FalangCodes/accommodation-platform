import Navbar from "./navbar";

export default function PageLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#F8F9FA]">
      <Navbar />
      <main>{children}</main>
    </div>
  );
}