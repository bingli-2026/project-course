import { Link, NavLink, Route, BrowserRouter as Router, Routes } from "react-router-dom";

import HistoryDetailPage from "./pages/HistoryDetailPage";
import HistoryListPage from "./pages/HistoryListPage";
import LiveDashboardPage from "./pages/LiveDashboardPage";

function App(): JSX.Element {
  return (
    <Router>
      <div style={{ fontFamily: "sans-serif", minHeight: "100vh", background: "#f5f5f5" }}>
        <header style={headerStyle}>
          <Link to="/" style={brandStyle}>双模态设备监测系统</Link>
          <nav style={navStyle}>
            <NavItem to="/">实时监测</NavItem>
            <NavItem to="/history">历史回放</NavItem>
          </nav>
        </header>
        <main style={{ padding: "16px", maxWidth: 1400, margin: "0 auto" }}>
          <Routes>
            <Route path="/" element={<LiveDashboardPage />} />
            <Route path="/history" element={<HistoryListPage />} />
            <Route path="/history/:sampleId" element={<HistoryDetailPage />} />
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
        background: isActive ? "#1677ff" : "transparent",
        fontSize: 14
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
