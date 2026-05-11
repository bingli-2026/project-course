import { Link, NavLink, Route, BrowserRouter as Router, Routes } from "react-router-dom";

import DashboardPage from "./pages/DashboardPage";
import SampleDetailPage from "./pages/SampleDetailPage";
import SamplesListPage from "./pages/SamplesListPage";

function App(): JSX.Element {
  return (
    <Router>
      <div style={{ fontFamily: "sans-serif", minHeight: "100vh", background: "#f6f7f9" }}>
        <header style={headerStyle}>
          <Link to="/" style={brandStyle}>双模态监测系统</Link>
          <nav style={navStyle}>
            <NavItem to="/">首页</NavItem>
            <NavItem to="/samples">样本</NavItem>
          </nav>
        </header>
        <main style={{ padding: "24px", maxWidth: 1200, margin: "0 auto" }}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/samples" element={<SamplesListPage />} />
            <Route path="/samples/:sampleId" element={<SampleDetailPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

function NavItem({ to, children }: { to: string; children: React.ReactNode }): JSX.Element {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      style={({ isActive }) => ({
        textDecoration: "none",
        padding: "6px 12px",
        borderRadius: 6,
        color: isActive ? "#fff" : "#cbd5e1",
        background: isActive ? "#2563eb" : "transparent"
      })}
    >
      {children}
    </NavLink>
  );
}

const headerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 24,
  padding: "12px 24px",
  background: "#1e293b",
  color: "#f8fafc"
};

const brandStyle: React.CSSProperties = {
  color: "#f8fafc",
  textDecoration: "none",
  fontWeight: 600,
  fontSize: 18
};

const navStyle: React.CSSProperties = {
  display: "flex",
  gap: 8
};

export default App;
