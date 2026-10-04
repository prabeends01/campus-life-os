import React, { useState, useEffect } from 'react';
import {
  BarChart3, Ticket, Shield, Bell, Sparkles, Layers, Users, FileCheck,
  UploadCloud, CheckSquare, MessageSquare, Volume2, Wifi, Phone,
  AlertTriangle, CheckCircle2, Clock, Flame, ChevronRight, X, Plus,
  Send, RefreshCw, Eye, ArrowRight, CornerDownRight
} from 'lucide-react';
import CampusMapViewer from '../map/CampusMapViewer';
import { useAuth, DEMO_CREDENTIALS } from '../context/AuthContext';
import { useApp } from '../context/AppContext';
import { api } from '../lib/api';

export default function AdminDashboard({ onSwitchToStudent }) {
  const { user, login } = useAuth();
  const { language, setLanguage, lowBandwidthMode, toggleLowBandwidth, setShowSmsSimulator, setShowVoiceModal } = useApp();

  // Active page: 'ct' (Control Tower), 'tickets', 'gatepass', 'notices', 'incidents', 'xray', 'staffload', 'approvals', 'migration', 'adoption'
  const [currentPage, setCurrentPage] = useState('ct');

  // Live state
  const [analytics, setAnalytics] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [gatePasses, setGatePasses] = useState([]);
  const [notices, setNotices] = useState([]);
  const [certificates, setCertificates] = useState([]);
  const [halls, setHalls] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);

  // Ticket filters
  const [ticketFilter, setTicketFilter] = useState('All');

  // Notice composer
  const [noticeTarget, setNoticeTarget] = useState('ALL');
  const [noticeTargetVal, setNoticeTargetVal] = useState('ALL');
  const [noticeTitle, setNoticeTitle] = useState('');
  const [noticePrio, setNoticePrio] = useState('NORMAL');
  const [noticeBody, setNoticeBody] = useState('');

  // CSV Migration Wizard state
  const [csvText, setCsvText] = useState('');
  const [csvPreview, setCsvPreview] = useState(null);
  const [importedCount, setImportedCount] = useState(148);

  // WhatsApp Import state
  const [waText, setWaText] = useState('');

  useEffect(() => {
    loadAllData();
    const interval = setInterval(loadAllData, 2500); // 2.5s auto-refresh as in prototype!
    return () => clearInterval(interval);
  }, []);

  const loadAllData = async () => {
    try {
      const [anData, tList, gpList, nList, certList, hList, incList] = await Promise.all([
        api.getAdminAnalytics(),
        api.getStaffTickets(),
        api.getStaffGatePassQueue(),
        api.getNoticesAnalytics(),
        api.getAdminCertificates(),
        api.getMessHalls(),
        api.getIncidents()
      ]);
      setAnalytics(anData);
      setTickets(tList);
      setGatePasses(gpList);
      setNotices(nList);
      setCertificates(certList);
      setHalls(hList);
      setIncidents(incList);
    } catch (e) {
      console.error("Admin poll error:", e);
    } finally {
      setLoading(false);
    }
  };

  // Actions
  const handleAssignTicket = async (ticketId, staffName) => {
    try {
      const staffUser = analytics?.staff_workload?.find(s => s.name === staffName);
      await api.updateTicketStatus(ticketId, 'ASSIGNED', `Assigned to ${staffName}`, staffUser?.staff_id);
      loadAllData();
    } catch (e) {
      alert(e.message);
    }
  };

  const handleUpdateTicketStatus = async (ticketId, status) => {
    try {
      const note = status === 'RESOLVED' ? 'Repairs completed & verified with photo proof' : 'Technician dispatched';
      await api.updateTicketStatus(ticketId, status, note);
      loadAllData();
    } catch (e) {
      alert(e.message);
    }
  };

  const handleMergeCluster = async (alertItem) => {
    try {
      await api.mergeIncidents({
        complaint_ids: alertItem.complaint_ids,
        title: alertItem.title,
        category: alertItem.category,
        place: alertItem.place,
        description: `Consolidated incident declared by Administrator for ${alertItem.place} Room ${alertItem.room}.`
      });
      alert(`Merged into Incident: "${alertItem.title}"! Staff alerted.`);
      loadAllData();
    } catch (e) {
      alert(e.message);
    }
  };

  const handleSendNotice = async (e) => {
    e.preventDefault();
    if (!noticeTitle || !noticeBody) return;
    try {
      await api.composeNotice({
        title: noticeTitle,
        body: noticeBody,
        target_type: noticeTarget,
        target_value: noticeTargetVal,
        priority: noticePrio
      });
      setNoticeTitle('');
      setNoticeBody('');
      alert("Targeted notice published across campus!");
      loadAllData();
    } catch (e) {
      alert(e.message);
    }
  };

  // CSV Ingestion simulation
  const handleLoadSampleCsv = () => {
    const sample = `Name,Roll No.,Hostel Room,Dept,Mobile\nAnanya Patel,2201CS014,Aryabhatta-304,CSE,9437011111\nRohan Singh,2201ME022,Aryabhatta-115,ME,9437022222\nPriya Rout,2201EC031,Gargi-210,ECE,9437033333\nAnanya Patel,2201CS014,Aryabhatta-304,CSE,9437011111\nSuman Das,,Aryabhatta-112,CE,9437044444`;
    setCsvText(sample);
    parseCsv(sample);
  };

  const parseCsv = (text) => {
    const lines = text.trim().split(/\r?\n/).map(l => l.split(',').map(c => c.trim()));
    if (lines.length < 2) {
      setCsvPreview(null);
      return;
    }
    const headers = lines[0];
    const rows = lines.slice(1);
    let valid = 0, duplicates = 0, missing = 0;
    const seenRolls = new Set();

    rows.forEach(r => {
      const name = r[0];
      const roll = r[1];
      if (!name || !roll) {
        missing++;
        return;
      }
      if (seenRolls.has(roll)) {
        duplicates++;
        return;
      }
      seenRolls.add(roll);
      valid++;
    });

    setCsvPreview({ headers, totalRows: rows.length, valid, duplicates, missing });
  };

  const handleCommitMigration = () => {
    if (!csvPreview) return;
    setImportedCount(prev => prev + csvPreview.valid);
    alert(`Successfully imported ${csvPreview.valid} student records. Duplicates flagged and resolved.`);
    setCsvText('');
    setCsvPreview(null);
  };

  const handleConvertWhatsApp = async () => {
    if (!waText.trim()) return;
    try {
      await api.composeNotice({
        title: "Imported Notice from Hostel WhatsApp Group",
        body: waText.trim(),
        target_type: "HOSTEL",
        target_value: "Aryabhatta Hall",
        priority: "NORMAL"
      });
      setWaText('');
      alert("WhatsApp announcement converted into official tracked notice!");
      loadAllData();
    } catch (e) {
      alert(e.message);
    }
  };

  // Calculations for Control Tower
  const openTickets = tickets.filter(t => t.status !== 'RESOLVED');
  const criticalCount = openTickets.filter(t => t.priority === 'CRITICAL' || t.priority === 'HIGH').length;
  const mediumCount = openTickets.filter(t => t.priority === 'MEDIUM').length;
  const lowCount = openTickets.filter(t => t.priority === 'LOW').length;

  const ageing72 = analytics?.ageing_heatmap?.over_72h || 0;
  const ageing48 = analytics?.ageing_heatmap?.between_48h_72h || 0;
  const ageing24 = analytics?.ageing_heatmap?.under_24h || 0;

  // Heatmap Places & Categories matrix (Section 8 & standalone structure)
  const heatmapPlaces = ["Hostel A", "Hostel B", "Hostel C", "Mess Hall", "Academic Block", "Library"];
  const heatmapCategories = ["Plumb", "Elect", "Mess", "Clean", "Other"];

  // Mapping open ticket ages to place x category
  const getOldestAge = (placeName, catPrefix) => {
    const matching = openTickets.filter(t => {
      const matchP = t.place.toLowerCase().includes(placeName.toLowerCase()) ||
        (placeName === "Hostel B" && t.place.includes("Aryabhatta")) ||
        (placeName === "Hostel A" && t.place.includes("Gargi")) ||
        (placeName === "Mess Hall" && (t.place.includes("Mess") || t.category === "Mess"));
      const matchC = t.category.toLowerCase().startsWith(catPrefix.toLowerCase());
      return matchP && matchC;
    });

    if (matching.length === 0) return null;
    return Math.max(...matching.map(t => t.age_hours || 1));
  };

  const getHeatmapColor = (age) => {
    if (!age) return 'transparent';
    if (age > 72) return 'var(--color-semantic-red)';
    if (age > 48) return 'var(--color-semantic-amber)';
    if (age > 24) return '#FBBF24';
    return 'var(--color-semantic-green)';
  };

  // Filtered tickets
  const filteredTickets = tickets.filter(t => {
    if (ticketFilter === 'All') return true;
    if (ticketFilter === 'Overdue') return t.status !== 'RESOLVED' && (t.age_hours > 48 || t.ageing_bucket === '>72h');
    return t.category.toLowerCase().includes(ticketFilter.toLowerCase());
  });

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', minHeight: '100vh', backgroundColor: 'var(--color-surface-bg)' }}>
      {/* ================= LEFT SIDEBAR (Matching Structure from Image 2 & Standalone) ================= */}
      <aside style={{
        backgroundColor: '#FFFFFF',
        borderRight: '1px solid var(--color-neutral-light)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        position: 'sticky',
        top: 0,
        overflowY: 'auto'
      }}>
        {/* Brand Header */}
        <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--color-neutral-light)', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            backgroundColor: 'var(--color-primary)', color: '#FFFFFF',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 800, fontSize: '18px', boxShadow: 'var(--shadow-md)'
          }}>
            C
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '15px', color: 'var(--color-ink)' }}>CampusOS</div>
            <div style={{ fontSize: '10px', color: 'var(--color-neutral-mid)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
              PROTOTYPE V1.0
            </div>
          </div>
        </div>

        {/* Role Switcher (Student / Admin) */}
        <div style={{
          margin: '14px 14px 8px',
          padding: '4px',
          backgroundColor: 'var(--color-surface-bg)',
          borderRadius: 'var(--radius-md)',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '4px',
          border: '1px solid var(--color-neutral-light)'
        }}>
          <button
            onClick={async () => {
              const cred = DEMO_CREDENTIALS.STUDENT;
              await login(cred.email, cred.pass, 'STUDENT');
            }}
            style={{
              padding: '8px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '12px',
              fontWeight: 600,
              backgroundColor: 'transparent',
              color: 'var(--color-neutral-mid)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px'
            }}
          >
            👤 Student
          </button>
          <button
            style={{
              padding: '8px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '12px',
              fontWeight: 700,
              backgroundColor: 'var(--color-primary)',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            🏛️ Admin
          </button>
        </div>

        {/* Nav Items Grouped */}
        <div style={{ flex: 1, padding: '10px', overflowY: 'auto' }}>
          {/* OVERVIEW GROUP */}
          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '10px', color: 'var(--color-neutral-mid)', textTransform: 'uppercase', letterSpacing: '0.12em', padding: '6px 12px', fontWeight: 800 }}>
              OVERVIEW
            </div>

            <button
              onClick={() => setCurrentPage('ct')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: currentPage === 'ct' ? 700 : 500,
                backgroundColor: currentPage === 'ct' ? 'var(--color-primary-light)' : 'transparent',
                color: currentPage === 'ct' ? 'var(--color-primary)' : 'var(--color-ink)',
                borderLeft: currentPage === 'ct' ? '3px solid var(--color-primary)' : '3px solid transparent',
                textAlign: 'left', marginBottom: '2px'
              }}
            >
              <BarChart3 size={16} /> Control Tower
            </button>

            <button
              onClick={() => setCurrentPage('tickets')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: currentPage === 'tickets' ? 700 : 500,
                backgroundColor: currentPage === 'tickets' ? 'var(--color-primary-light)' : 'transparent',
                color: currentPage === 'tickets' ? 'var(--color-primary)' : 'var(--color-ink)',
                borderLeft: currentPage === 'tickets' ? '3px solid var(--color-primary)' : '3px solid transparent',
                textAlign: 'left', marginBottom: '2px'
              }}
            >
              <Ticket size={16} /> Tickets
              <span className="status-pill red" style={{ marginLeft: 'auto', padding: '2px 6px', fontSize: '10px' }}>
                {openTickets.length}
              </span>
            </button>

            <button
              onClick={() => setCurrentPage('gatepass')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: currentPage === 'gatepass' ? 700 : 500,
                backgroundColor: currentPage === 'gatepass' ? 'var(--color-primary-light)' : 'transparent',
                color: currentPage === 'gatepass' ? 'var(--color-primary)' : 'var(--color-ink)',
                borderLeft: currentPage === 'gatepass' ? '3px solid var(--color-primary)' : '3px solid transparent',
                textAlign: 'left', marginBottom: '2px'
              }}
            >
              <Shield size={16} /> Gate Passes
              <span className="status-pill blue" style={{ marginLeft: 'auto', padding: '2px 6px', fontSize: '10px' }}>
                {gatePasses.filter(g => g.status === 'PENDING').length}
              </span>
            </button>

            <button
              onClick={() => setCurrentPage('notices')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: currentPage === 'notices' ? 700 : 500,
                backgroundColor: currentPage === 'notices' ? 'var(--color-primary-light)' : 'transparent',
                color: currentPage === 'notices' ? 'var(--color-primary)' : 'var(--color-ink)',
                borderLeft: currentPage === 'notices' ? '3px solid var(--color-primary)' : '3px solid transparent',
                textAlign: 'left', marginBottom: '2px'
              }}
            >
              <Bell size={16} /> Notice Center
            </button>

            <button
              onClick={() => setCurrentPage('incidents')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: currentPage === 'incidents' ? 700 : 500,
                backgroundColor: currentPage === 'incidents' ? 'var(--color-primary-light)' : 'transparent',
                color: currentPage === 'incidents' ? 'var(--color-primary)' : 'var(--color-ink)',
                borderLeft: currentPage === 'incidents' ? '3px solid var(--color-primary)' : '3px solid transparent',
                textAlign: 'left', marginBottom: '2px'
              }}
            >
              <Sparkles size={16} /> Incidents
            </button>
          </div>

          {/* CAMPUS GROUP */}
          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '10px', color: 'var(--color-neutral-mid)', textTransform: 'uppercase', letterSpacing: '0.12em', padding: '6px 12px', fontWeight: 800 }}>
              CAMPUS
            </div>

            <button
              onClick={() => setCurrentPage('xray')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: currentPage === 'xray' ? 700 : 500,
                backgroundColor: currentPage === 'xray' ? 'var(--color-primary-light)' : 'transparent',
                color: currentPage === 'xray' ? 'var(--color-primary)' : 'var(--color-ink)',
                borderLeft: currentPage === 'xray' ? '3px solid var(--color-primary)' : '3px solid transparent',
                textAlign: 'left', marginBottom: '2px'
              }}
            >
              <Layers size={16} /> X-Ray 3D
            </button>

            <button
              onClick={() => setCurrentPage('staffload')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: currentPage === 'staffload' ? 700 : 500,
                backgroundColor: currentPage === 'staffload' ? 'var(--color-primary-light)' : 'transparent',
                color: currentPage === 'staffload' ? 'var(--color-primary)' : 'var(--color-ink)',
                borderLeft: currentPage === 'staffload' ? '3px solid var(--color-primary)' : '3px solid transparent',
                textAlign: 'left', marginBottom: '2px'
              }}
            >
              <Users size={16} /> Staff Load
            </button>

            <button
              onClick={() => setCurrentPage('approvals')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: currentPage === 'approvals' ? 700 : 500,
                backgroundColor: currentPage === 'approvals' ? 'var(--color-primary-light)' : 'transparent',
                color: currentPage === 'approvals' ? 'var(--color-primary)' : 'var(--color-ink)',
                borderLeft: currentPage === 'approvals' ? '3px solid var(--color-primary)' : '3px solid transparent',
                textAlign: 'left', marginBottom: '2px'
              }}
            >
              <FileCheck size={16} /> Approvals
            </button>
          </div>

          {/* MANAGE GROUP */}
          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '10px', color: 'var(--color-neutral-mid)', textTransform: 'uppercase', letterSpacing: '0.12em', padding: '6px 12px', fontWeight: 800 }}>
              MANAGE
            </div>

            <button
              onClick={() => setCurrentPage('migration')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: currentPage === 'migration' ? 700 : 500,
                backgroundColor: currentPage === 'migration' ? 'var(--color-primary-light)' : 'transparent',
                color: currentPage === 'migration' ? 'var(--color-primary)' : 'var(--color-ink)',
                borderLeft: currentPage === 'migration' ? '3px solid var(--color-primary)' : '3px solid transparent',
                textAlign: 'left', marginBottom: '2px'
              }}
            >
              <UploadCloud size={16} /> Data Migration
            </button>

            <button
              onClick={() => setCurrentPage('adoption')}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 12px',
                borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: currentPage === 'adoption' ? 700 : 500,
                backgroundColor: currentPage === 'adoption' ? 'var(--color-primary-light)' : 'transparent',
                color: currentPage === 'adoption' ? 'var(--color-primary)' : 'var(--color-ink)',
                borderLeft: currentPage === 'adoption' ? '3px solid var(--color-primary)' : '3px solid transparent',
                textAlign: 'left', marginBottom: '2px'
              }}
            >
              <CheckSquare size={16} /> Adoption Plan
            </button>
          </div>
        </div>

        {/* Sidebar Footer User */}
        <div style={{ padding: '14px', borderTop: '1px solid var(--color-neutral-light)', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '34px', height: '34px', borderRadius: '50%',
            backgroundColor: 'var(--color-primary)', color: '#FFFFFF',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 800, fontSize: '14px', flexShrink: 0
          }}>
            S
          </div>
          <div style={{ overflow: 'hidden' }}>
            <div style={{ fontSize: '13px', fontWeight: 700, whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
              Dr. S. Mohanty
            </div>
            <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)' }}>Dean · Admin</div>
          </div>
        </div>
      </aside>

      {/* ================= MAIN COLUMN ================= */}
      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, height: '100vh', overflowY: 'auto' }}>
        {/* Top Header Bar */}
        <header style={{
          backgroundColor: '#FFFFFF',
          borderBottom: '1px solid var(--color-neutral-light)',
          height: '60px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          position: 'sticky',
          top: 0,
          zIndex: 100
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 800, color: 'var(--color-ink)' }}>
              {currentPage === 'ct' && 'Control Tower'}
              {currentPage === 'tickets' && 'Tickets'}
              {currentPage === 'gatepass' && 'Gate Passes'}
              {currentPage === 'notices' && 'Notice Center'}
              {currentPage === 'incidents' && 'Incidents'}
              {currentPage === 'xray' && 'X-Ray 3D'}
              {currentPage === 'staffload' && 'Staff Workload'}
              {currentPage === 'approvals' && 'Certificate Approvals'}
              {currentPage === 'migration' && 'Data Migration'}
              {currentPage === 'adoption' && 'Adoption Plan'}
            </h2>
          </div>

          {/* Quick Header Tools (matching image 2: Mute, Lang dropdown, Wi-Fi, Phone, Bell) */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => setShowVoiceModal(true)}
              title="Voice Assistant"
              style={{
                width: '36px', height: '36px', borderRadius: '8px',
                border: '1px solid var(--color-neutral-light)', backgroundColor: 'var(--color-surface-bg)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-ink)'
              }}
            >
              <Volume2 size={16} />
            </button>

            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              style={{
                padding: '6px 10px', borderRadius: '8px', border: '1px solid var(--color-neutral-light)',
                backgroundColor: 'var(--color-surface-bg)', fontSize: '12px', fontWeight: 700, color: 'var(--color-ink)'
              }}
            >
              <option value="en">EN ⌵</option>
              <option value="hi">HI ⌵</option>
              <option value="or">OR ⌵</option>
            </select>

            <button
              onClick={toggleLowBandwidth}
              title={lowBandwidthMode ? "Low Bandwidth Mode ON" : "Normal High Speed"}
              style={{
                width: '36px', height: '36px', borderRadius: '8px',
                border: '1px solid var(--color-neutral-light)',
                backgroundColor: lowBandwidthMode ? 'var(--color-semantic-amber-bg)' : 'var(--color-surface-bg)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: lowBandwidthMode ? 'var(--color-semantic-amber)' : 'var(--color-ink)'
              }}
            >
              <Wifi size={16} />
            </button>

            <button
              onClick={() => setShowSmsSimulator(true)}
              title="SMS Simulator"
              style={{
                width: '36px', height: '36px', borderRadius: '8px',
                border: '1px solid var(--color-neutral-light)', backgroundColor: 'var(--color-surface-bg)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-ink)'
              }}
            >
              <Phone size={16} />
            </button>

            <button
              onClick={() => setCurrentPage('notices')}
              title="Notifications"
              style={{
                width: '36px', height: '36px', borderRadius: '8px',
                border: '1px solid var(--color-neutral-light)', backgroundColor: 'var(--color-surface-bg)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-ink)',
                position: 'relative'
              }}
            >
              <Bell size={16} />
              <span style={{ position: 'absolute', top: '7px', right: '7px', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--color-semantic-red)' }} />
            </button>
          </div>
        </header>

        {/* Page Content Body */}
        <main style={{ padding: '24px 28px', flex: 1 }}>

          {/* ================= TAB 1: CONTROL TOWER (Exact Match to Image 2) ================= */}
          {currentPage === 'ct' && (
            <div>
              <div style={{ marginBottom: '22px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--color-ink)' }}>Control Tower</h1>
                <p style={{ fontSize: '13px', color: 'var(--color-neutral-mid)', marginTop: '2px' }}>
                  Live from the same data students write to · auto-refresh 2.5s
                </p>
              </div>

              {/* 1. TOP 4 KPI CARDS (grid-4 matching image 2) */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '14px' }}>
                {/* KPI 1: PENDING */}
                <div style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--color-neutral-light)', borderTop: '3px solid var(--color-primary)', borderRadius: '14px', padding: '16px', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--color-neutral-mid)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>PENDING</div>
                  <div style={{ fontSize: '28px', fontWeight: 800, margin: '6px 0 4px', color: 'var(--color-ink)' }}>{openTickets.length}</div>
                  <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ color: 'var(--color-semantic-red)' }}>● {criticalCount} high</span> · <span style={{ color: 'var(--color-semantic-amber)' }}>● {mediumCount} med</span> · <span style={{ color: 'var(--color-semantic-green)' }}>● {lowCount} low</span>
                  </div>
                </div>

                {/* KPI 2: AGEING */}
                <div style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--color-neutral-light)', borderTop: '3px solid var(--color-semantic-amber)', borderRadius: '14px', padding: '16px', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--color-neutral-mid)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>AGEING</div>
                  <div style={{ fontSize: '28px', fontWeight: 800, margin: '6px 0 4px', color: 'var(--color-ink)' }}>{ageing72 + ageing48}</div>
                  <div style={{ fontSize: '11px', color: 'var(--color-semantic-red)' }}>
                    {ageing72} &gt;72h · {ageing48} &gt;48h · {ageing24} &lt;24h
                  </div>
                </div>

                {/* KPI 3: AVG RESOLUTION */}
                <div style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--color-neutral-light)', borderTop: '3px solid #2563EB', borderRadius: '14px', padding: '16px', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--color-neutral-mid)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>AVG RESOLUTION</div>
                  <div style={{ fontSize: '28px', fontWeight: 800, margin: '6px 0 4px', color: 'var(--color-ink)' }}>7.3h</div>
                  <div style={{ fontSize: '11px', color: 'var(--color-semantic-green)' }}>3 resolved</div>
                </div>

                {/* KPI 4: WITHIN SLA */}
                <div style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--color-neutral-light)', borderTop: '3px solid var(--color-semantic-green)', borderRadius: '14px', padding: '16px', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--color-neutral-mid)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>WITHIN SLA</div>
                  <div style={{ fontSize: '28px', fontWeight: 800, margin: '6px 0 4px', color: 'var(--color-ink)' }}>100%</div>
                  <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)' }}>target 90%</div>
                </div>
              </div>

              {/* 2. MIDDLE ROW (grid-2 matching image 2: Ageing heatmap + Workload distribution) */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '14px', marginBottom: '14px' }}>
                {/* Ageing Heatmap Card */}
                <div style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--color-neutral-light)', borderRadius: '14px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-ink)' }}>Ageing heatmap</h3>
                    <span style={{ fontSize: '11px', color: 'var(--color-neutral-mid)', fontFamily: 'var(--font-mono)' }}>
                      oldest open · place x category
                    </span>
                  </div>

                  {/* 2D Heatmap Grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: '110px repeat(5, 1fr)', gap: '6px', textAlign: 'center', fontSize: '11px' }}>
                    <div></div>
                    {heatmapCategories.map(c => (
                      <div key={c} style={{ color: 'var(--color-neutral-mid)', fontSize: '10px', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                        {c}
                      </div>
                    ))}

                    {heatmapPlaces.map(place => (
                      <React.Fragment key={place}>
                        <div style={{ fontSize: '11px', padding: '8px 0', textAlign: 'left', fontWeight: 600, color: 'var(--color-ink)' }}>
                          {place}
                        </div>
                        {heatmapCategories.map(cat => {
                          const age = getOldestAge(place, cat);
                          const bg = getHeatmapColor(age);
                          return (
                            <div
                              key={cat}
                              style={{
                                backgroundColor: bg,
                                color: age ? '#FFFFFF' : 'var(--color-neutral-mid)',
                                borderRadius: '6px',
                                padding: '6px 2px',
                                fontWeight: 700,
                                fontSize: '11px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center'
                              }}
                            >
                              {age ? `${Math.round(age)}h` : '·'}
                            </div>
                          );
                        })}
                      </React.Fragment>
                    ))}
                  </div>
                </div>

                {/* Workload Distribution Card */}
                <div style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--color-neutral-light)', borderRadius: '14px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-ink)' }}>Workload distribution</h3>
                    <span style={{ fontSize: '11px', color: 'var(--color-neutral-mid)', fontFamily: 'var(--font-mono)' }}>
                      open tickets / staff (cap 5)
                    </span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {[
                      { initial: 'R', name: 'Raju', dept: 'Maintenance · IT', load: 2, cap: 5 },
                      { initial: 'S', name: 'Suresh', dept: 'Electrical · Maintenance', load: 1, cap: 5 },
                      { initial: 'A', name: 'Anita', dept: 'Mess · Housekeeping', load: 0, cap: 5 }
                    ].map(staff => (
                      <div key={staff.name} style={{ display: 'grid', gridTemplateColumns: '36px 1fr 100px 30px', alignItems: 'center', gap: '10px' }}>
                        <div style={{
                          width: '34px', height: '34px', borderRadius: '50%',
                          backgroundColor: 'var(--color-primary-light)', color: 'var(--color-primary)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: '13px'
                        }}>
                          {staff.initial}
                        </div>
                        <div>
                          <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-ink)' }}>{staff.name}</div>
                          <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)' }}>{staff.dept}</div>
                        </div>
                        <div>
                          <div style={{ width: '100%', height: '6px', backgroundColor: 'var(--color-surface-bg)', borderRadius: '3px', overflow: 'hidden' }}>
                            <div style={{ width: `${(staff.load / staff.cap) * 100}%`, height: '100%', backgroundColor: 'var(--color-primary)' }} />
                          </div>
                          <div style={{ fontSize: '10px', color: 'var(--color-neutral-mid)', textAlign: 'right', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                            {staff.load}/{staff.cap}
                          </div>
                        </div>
                        <div style={{ fontSize: '14px', fontWeight: 800, textAlign: 'right', color: 'var(--color-ink)' }}>
                          {staff.load}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 3. BOTTOM ROW (grid-3 matching image 2: Recurring issues, Resolution time, Notice read rate) */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', marginBottom: '16px' }}>
                {/* Recurring Issues */}
                <div style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--color-neutral-light)', borderRadius: '14px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-ink)' }}>Recurring issues</h3>
                  </div>

                  <div style={{
                    backgroundColor: 'var(--color-surface-bg)',
                    borderRadius: '10px',
                    padding: '12px',
                    border: '1px solid var(--color-neutral-light)'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-ink)' }}>
                        🔁 Plumbing · Hostel B · Room 302
                      </span>
                      <span className="status-pill amber" style={{ fontSize: '10px', padding: '2px 6px' }}>
                        3 this month
                      </span>
                    </div>
                    <p style={{ fontSize: '12px', color: 'var(--color-neutral-mid)', lineHeight: '1.4' }}>
                      Room 302 (Hostel B) has had 3 plumbing complaints this month — inspect root cause.
                    </p>
                    <button
                      onClick={() => handleMergeCluster({
                        complaint_ids: [1, 2, 4],
                        title: "Chronic Plumbing Breakdown: Hostel B Room 302",
                        category: "Plumbing",
                        place: "Hostel B",
                        room: "302"
                      })}
                      className="btn-primary"
                      style={{ fontSize: '11px', padding: '6px 10px', marginTop: '10px', width: 'auto' }}
                    >
                      Declare Confirmed Incident
                    </button>
                  </div>
                </div>

                {/* Resolution Time By Category & Gate Pass Monitor */}
                <div style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--color-neutral-light)', borderRadius: '14px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ marginBottom: '14px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-ink)', marginBottom: '10px' }}>
                      Resolution time by category
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '2px' }}>
                          <span>Plumbing</span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>10.0h</span>
                        </div>
                        <div style={{ width: '100%', height: '5px', backgroundColor: 'var(--color-surface-bg)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ width: '80%', height: '100%', backgroundColor: 'var(--color-primary)' }} />
                        </div>
                      </div>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '2px' }}>
                          <span>Electrical</span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>3.0h</span>
                        </div>
                        <div style={{ width: '100%', height: '5px', backgroundColor: 'var(--color-surface-bg)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ width: '25%', height: '100%', backgroundColor: '#2563EB' }} />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div style={{ borderTop: '1px solid var(--color-neutral-light)', paddingTop: '10px' }}>
                    <h4 style={{ fontSize: '13px', fontWeight: 700, marginBottom: '4px' }}>Gate pass monitor</h4>
                    <div style={{ fontSize: '12px', color: 'var(--color-neutral-mid)' }}>
                      1 students out · <span style={{ color: 'var(--color-semantic-red)', fontWeight: 700 }}>0 overdue</span>
                    </div>
                  </div>
                </div>

                {/* Notice Read Rate & Today's Mess Feedback */}
                <div style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--color-neutral-light)', borderRadius: '14px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
                  <div style={{ marginBottom: '14px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-ink)', marginBottom: '6px' }}>
                      Notice read rate
                    </h3>
                    <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--color-primary)' }}>
                      92%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)', lineHeight: '1.3' }}>
                      "DBMS Lab cancelled - rescheduled to Thursday" — BATCH: CSE-3
                    </div>
                  </div>

                  <div style={{ borderTop: '1px solid var(--color-neutral-light)', paddingTop: '10px' }}>
                    <h4 style={{ fontSize: '13px', fontWeight: 700, marginBottom: '4px' }}>Today's mess feedback</h4>
                    <div style={{ fontSize: '12px', color: 'var(--color-neutral-mid)' }}>
                      14 votes · <span style={{ color: 'var(--color-semantic-green)', fontWeight: 700 }}>71% good</span> · <span style={{ color: 'var(--color-semantic-red)' }}>4 issues</span> (cold 2, salty 2)
                    </div>
                  </div>
                </div>
              </div>

              {/* Bottom Quick Links */}
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={() => setCurrentPage('xray')}
                  className="btn-primary"
                  style={{ width: 'auto', padding: '10px 18px', fontSize: '13px' }}
                >
                  🔮 Open 3D X-Ray / Hologram
                </button>
                <button
                  onClick={() => setCurrentPage('tickets')}
                  className="btn-secondary"
                  style={{ width: 'auto', padding: '10px 18px', fontSize: '13px' }}
                >
                  Manage tickets →
                </button>
              </div>
            </div>
          )}

          {/* ================= TAB 2: TICKETS ================= */}
          {currentPage === 'tickets' && (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Tickets Queue</h1>
                <p style={{ fontSize: '13px', color: 'var(--color-neutral-mid)' }}>
                  Assign · progress · resolve with proof · full audit trail · 48h auto-escalation
                </p>
              </div>

              {/* Filter Chips Bar */}
              <div style={{ display: 'flex', gap: '6px', marginBottom: '16px', flexWrap: 'wrap' }}>
                {['All', 'Overdue', 'Plumbing', 'Electrical', 'Mess', 'Cleanliness', 'IT'].map(f => (
                  <button
                    key={f}
                    onClick={() => setTicketFilter(f)}
                    style={{
                      padding: '6px 14px',
                      borderRadius: 'var(--radius-full)',
                      fontSize: '12px',
                      fontWeight: 600,
                      backgroundColor: ticketFilter === f ? 'var(--color-primary)' : '#FFFFFF',
                      color: ticketFilter === f ? '#FFFFFF' : 'var(--color-ink)',
                      border: '1px solid var(--color-neutral-light)'
                    }}
                  >
                    {f}
                  </button>
                ))}
              </div>

              {/* Tickets List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {filteredTickets.map(t => {
                  const isResolved = t.status === 'RESOLVED';
                  return (
                    <div key={t.id} className="category-card cat-plumbing" style={{ borderLeftColor: isResolved ? 'var(--color-semantic-green)' : 'var(--color-primary)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
                        <div>
                          <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)', fontFamily: 'var(--font-mono)' }}>
                            #{t.id} · {t.category} · {t.place} Room {t.room}
                          </div>
                          <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--color-ink)', marginTop: '2px' }}>
                            {t.title}
                          </h4>
                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '4px' }}>
                            <span className={`status-pill ${t.priority === 'CRITICAL' ? 'red' : t.priority === 'HIGH' ? 'amber' : 'blue'}`}>
                              {t.priority}
                            </span>
                            <span style={{ fontSize: '11px', color: 'var(--color-neutral-mid)' }}>
                              SLA: 12h
                            </span>
                          </div>
                        </div>

                        <div style={{ textAlign: 'right' }}>
                          <span className={`status-pill ${isResolved ? 'green' : 'amber'}`}>
                            {t.status}
                          </span>
                          <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)', marginTop: '4px' }}>
                            Age: {t.age_hours}h
                          </div>
                        </div>
                      </div>

                      <p style={{ fontSize: '13px', color: 'var(--color-neutral-mid)', marginBottom: '12px' }}>
                        {t.description}
                      </p>

                      {/* Controls */}
                      {!isResolved && (
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                          <select
                            onChange={(e) => handleAssignTicket(t.id, e.target.value)}
                            style={{ padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-neutral-light)', fontSize: '12px' }}
                          >
                            <option value="">Assign staff...</option>
                            <option value="Raju">Raju (Maintenance)</option>
                            <option value="Suresh">Suresh (Electrical)</option>
                            <option value="Anita">Anita (Housekeeping)</option>
                          </select>
                          <button
                            onClick={() => handleUpdateTicketStatus(t.id, 'IN_PROGRESS')}
                            className="btn-secondary"
                            style={{ padding: '6px 12px', fontSize: '12px' }}
                          >
                            Start work
                          </button>
                          <button
                            onClick={() => handleUpdateTicketStatus(t.id, 'RESOLVED')}
                            className="btn-primary"
                            style={{ width: 'auto', padding: '6px 14px', fontSize: '12px', backgroundColor: 'var(--color-semantic-green)' }}
                          >
                            Resolve + proof
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ================= TAB 3: GATE PASSES ================= */}
          {currentPage === 'gatepass' && (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Gate Pass Operations</h1>
                <p style={{ fontSize: '13px', color: 'var(--color-neutral-mid)' }}>
                  Approvals · guard QR scan log · overdue returns
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '20px' }}>
                <div style={{ backgroundColor: '#FFF', padding: '16px', borderRadius: '12px', border: '1px solid var(--color-neutral-light)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)', fontWeight: 700 }}>STUDENTS OUT NOW</div>
                  <div style={{ fontSize: '24px', fontWeight: 800, marginTop: '4px' }}>1</div>
                </div>
                <div style={{ backgroundColor: '#FFF', padding: '16px', borderRadius: '12px', border: '1px solid var(--color-neutral-light)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)', fontWeight: 700 }}>OVERDUE RETURNS</div>
                  <div style={{ fontSize: '24px', fontWeight: 800, marginTop: '4px', color: 'var(--color-semantic-red)' }}>0</div>
                </div>
                <div style={{ backgroundColor: '#FFF', padding: '16px', borderRadius: '12px', border: '1px solid var(--color-neutral-light)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)', fontWeight: 700 }}>PENDING APPROVAL</div>
                  <div style={{ fontSize: '24px', fontWeight: 800, marginTop: '4px', color: 'var(--color-primary)' }}>
                    {gatePasses.filter(g => g.status === 'PENDING').length}
                  </div>
                </div>
                <div style={{ backgroundColor: '#FFF', padding: '16px', borderRadius: '12px', border: '1px solid var(--color-neutral-light)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)', fontWeight: 700 }}>AUTO-APPROVED</div>
                  <div style={{ fontSize: '24px', fontWeight: 800, marginTop: '4px', color: 'var(--color-semantic-green)' }}>4</div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {gatePasses.map(gp => (
                  <div key={gp.id} className="category-card cat-it">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)' }}>#{gp.id} · {gp.status}</div>
                        <h4 style={{ fontSize: '15px', fontWeight: 700 }}>Destination: {gp.destination}</h4>
                        <div style={{ fontSize: '12px', color: 'var(--color-neutral-mid)' }}>Reason: {gp.reason}</div>
                      </div>
                      <span className={`status-pill ${gp.status === 'APPROVED' ? 'green' : 'amber'}`}>{gp.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ================= TAB 4: NOTICE CENTER ================= */}
          {currentPage === 'notices' && (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Notice Center</h1>
                <p style={{ fontSize: '13px', color: 'var(--color-neutral-mid)' }}>
                  Targeted push · read receipts · auto-reminder at 4h · SMS fallback
                </p>
              </div>

              {/* Composer */}
              <div style={{ backgroundColor: '#FFF', padding: '20px', borderRadius: '14px', border: '1px solid var(--color-neutral-light)', marginBottom: '20px' }}>
                <form onSubmit={handleSendNotice}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                    <div>
                      <label style={{ fontSize: '11px', fontWeight: 700, display: 'block', marginBottom: '4px' }}>Target</label>
                      <select value={noticeTarget} onChange={(e) => setNoticeTarget(e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid var(--color-neutral-light)' }}>
                        <option value="ALL">ALL</option>
                        <option value="BRANCH">BRANCH</option>
                        <option value="YEAR">YEAR</option>
                        <option value="HOSTEL">HOSTEL</option>
                        <option value="BATCH">BATCH</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: '11px', fontWeight: 700, display: 'block', marginBottom: '4px' }}>Value</label>
                      <input value={noticeTargetVal} onChange={(e) => setNoticeTargetVal(e.target.value)} placeholder="e.g. CSE, 3, Aryabhatta" style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid var(--color-neutral-light)' }} />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                    <div>
                      <label style={{ fontSize: '11px', fontWeight: 700, display: 'block', marginBottom: '4px' }}>Subject</label>
                      <input value={noticeTitle} onChange={(e) => setNoticeTitle(e.target.value)} required style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid var(--color-neutral-light)' }} />
                    </div>
                    <div>
                      <label style={{ fontSize: '11px', fontWeight: 700, display: 'block', marginBottom: '4px' }}>Priority</label>
                      <select value={noticePrio} onChange={(e) => setNoticePrio(e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid var(--color-neutral-light)' }}>
                        <option value="NORMAL">NORMAL</option>
                        <option value="URGENT">URGENT</option>
                        <option value="CRITICAL">CRITICAL</option>
                      </select>
                    </div>
                  </div>

                  <div style={{ marginBottom: '14px' }}>
                    <label style={{ fontSize: '11px', fontWeight: 700, display: 'block', marginBottom: '4px' }}>Message Body</label>
                    <textarea value={noticeBody} onChange={(e) => setNoticeBody(e.target.value)} rows={3} required style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid var(--color-neutral-light)' }} />
                  </div>

                  <button type="submit" className="btn-primary" style={{ width: 'auto', padding: '10px 24px' }}>
                    Send Notice
                  </button>
                </form>
              </div>

              {/* Notice List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {notices.map(n => (
                  <div key={n.id} style={{ backgroundColor: '#FFF', padding: '16px', borderRadius: '12px', border: '1px solid var(--color-neutral-light)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span className={`status-pill ${n.priority === 'CRITICAL' ? 'red' : 'blue'}`}>{n.priority}</span>
                      <span style={{ fontSize: '11px', color: 'var(--color-neutral-mid)' }}>Target: {n.target_type} ({n.target_value})</span>
                    </div>
                    <h4 style={{ fontSize: '15px', fontWeight: 700 }}>{n.title}</h4>
                    <p style={{ fontSize: '12px', color: 'var(--color-neutral-mid)', margin: '6px 0 10px' }}>{n.body}</p>
                    <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                      Read rate: {n.read_percentage}% ({n.read_count}/{n.total_target_count})
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ================= TAB 5: INCIDENTS ================= */}
          {currentPage === 'incidents' && (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Incidents Engine</h1>
                <p style={{ fontSize: '13px', color: 'var(--color-neutral-mid)' }}>
                  Same pattern engine from Ask Campus — related tickets clustered by place, category and time window
                </p>
              </div>

              <div style={{ backgroundColor: '#FFF', padding: '20px', borderRadius: '14px', border: '1px solid var(--color-neutral-light)', marginBottom: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '4px' }}>Potential Incidents (Auto-Detected)</h3>
                <p style={{ fontSize: '12px', color: 'var(--color-neutral-mid)', marginBottom: '14px' }}>≥3 related tickets within 2h or chronic 30d window</p>

                {analytics?.recurring_alerts?.map((al, idx) => (
                  <div key={idx} style={{ padding: '12px', backgroundColor: 'var(--color-surface-bg)', borderRadius: '10px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: 700 }}>{al.title}</div>
                      <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)' }}>{al.chronic_count} tickets detected in {al.place} {al.room}</div>
                    </div>
                    <button onClick={() => handleMergeCluster(al)} className="btn-primary" style={{ width: 'auto', padding: '6px 14px', fontSize: '12px' }}>
                      Merge to Incident
                    </button>
                  </div>
                ))}
              </div>

              <div style={{ backgroundColor: '#FFF', padding: '20px', borderRadius: '14px', border: '1px solid var(--color-neutral-light)' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '12px' }}>Confirmed Institutional Incidents</h3>
                {incidents.map(inc => (
                  <div key={inc.id} style={{ padding: '12px', borderLeft: '4px solid var(--color-semantic-red)', backgroundColor: 'var(--color-surface-bg)', borderRadius: '8px', marginBottom: '8px' }}>
                    <div style={{ fontSize: '14px', fontWeight: 700 }}>#{inc.id} · {inc.title}</div>
                    <div style={{ fontSize: '12px', color: 'var(--color-neutral-mid)' }}>Status: {inc.status} • Location: {inc.place}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ================= TAB 6: X-RAY 3D ================= */}
          {currentPage === 'xray' && (
            <div>
              <CampusMapViewer mode="xray" isAdmin={true} />
            </div>
          )}

          {/* ================= TAB 7: STAFF LOAD ================= */}
          {currentPage === 'staffload' && (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Staff Workload Command</h1>
                <p style={{ fontSize: '13px', color: 'var(--color-neutral-mid)' }}>
                  Workload balancing and ticket dispatch distribution
                </p>
              </div>

              <div style={{ backgroundColor: '#FFF', padding: '20px', borderRadius: '14px', border: '1px solid var(--color-neutral-light)', marginBottom: '14px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {analytics?.staff_workload?.map(s => (
                    <div key={s.staff_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', backgroundColor: 'var(--color-surface-bg)', borderRadius: '8px' }}>
                      <div>
                        <div style={{ fontSize: '14px', fontWeight: 700 }}>{s.name}</div>
                        <div style={{ fontSize: '12px', color: 'var(--color-neutral-mid)' }}>{s.email}</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <span className="status-pill blue">{s.active_tickets} active tickets</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ padding: '12px 16px', backgroundColor: 'var(--color-semantic-amber-bg)', border: '1px solid rgba(217, 119, 6, 0.3)', borderRadius: '10px', fontSize: '12px', color: 'var(--color-semantic-amber)' }}>
                <strong>Suggestion:</strong> Workload balanced across maintenance and electrical cells.
              </div>
            </div>
          )}

          {/* ================= TAB 8: APPROVALS (Certificates) ================= */}
          {currentPage === 'approvals' && (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Certificate Approvals</h1>
                <p style={{ fontSize: '13px', color: 'var(--color-neutral-mid)' }}>
                  Academic section clearance for Bonafide, Transcript, and Migration
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {certificates.map(c => (
                  <div key={c.id} className="category-card cat-it" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: '11px', color: 'var(--color-neutral-mid)' }}>APPLICATION #{c.id} · {c.type}</div>
                      <h4 style={{ fontSize: '15px', fontWeight: 700 }}>{c.student_name} ({c.student_roll})</h4>
                      <div style={{ fontSize: '12px', color: 'var(--color-neutral-mid)' }}>Purpose: {c.purpose}</div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <span className={`status-pill ${c.status === 'READY' ? 'green' : 'amber'}`}>{c.status}</span>
                      {c.status === 'PENDING' && (
                        <button onClick={async () => { await api.updateCertificateStatus(c.id, 'PROCESSING'); loadAllData(); }} className="btn-primary" style={{ width: 'auto', padding: '6px 12px', fontSize: '12px' }}>
                          Process
                        </button>
                      )}
                      {c.status === 'PROCESSING' && (
                        <button onClick={async () => { await api.updateCertificateStatus(c.id, 'READY'); loadAllData(); }} className="btn-primary" style={{ width: 'auto', padding: '6px 12px', fontSize: '12px', backgroundColor: 'var(--color-semantic-green)' }}>
                          Mark Ready
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ================= TAB 9: DATA MIGRATION ================= */}
          {currentPage === 'migration' && (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Data Migration</h1>
                <p style={{ fontSize: '13px', color: 'var(--color-neutral-mid)' }}>
                  Excel/CSV registers + WhatsApp exports → CampusOS · imported: <b>{importedCount}</b>
                </p>
              </div>

              {/* 1. CSV Student Register */}
              <div style={{ backgroundColor: '#FFF', padding: '20px', borderRadius: '14px', border: '1px solid var(--color-neutral-light)', marginBottom: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <h3 style={{ fontSize: '15px', fontWeight: 700 }}>1 · Student Register (CSV)</h3>
                  <button onClick={handleLoadSampleCsv} className="btn-secondary" style={{ fontSize: '12px', padding: '6px 12px' }}>
                    Load Sample CSV
                  </button>
                </div>
                <textarea
                  value={csvText}
                  onChange={(e) => { setCsvText(e.target.value); parseCsv(e.target.value); }}
                  placeholder="Paste CSV rows (Name, Roll No., Hostel Room, Dept, Mobile)..."
                  rows={4}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--color-neutral-light)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}
                />

                {csvPreview && (
                  <div style={{ marginTop: '14px', padding: '14px', backgroundColor: 'var(--color-surface-bg)', borderRadius: '10px' }}>
                    <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '8px' }}>Column Mapping & Integrity Wizard</div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginBottom: '12px' }}>
                      <div style={{ backgroundColor: '#FFF', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                        <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--color-semantic-green)' }}>{csvPreview.valid}</div>
                        <div style={{ fontSize: '10px', color: 'var(--color-neutral-mid)' }}>VALID ROWS</div>
                      </div>
                      <div style={{ backgroundColor: '#FFF', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                        <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--color-semantic-amber)' }}>{csvPreview.duplicates}</div>
                        <div style={{ fontSize: '10px', color: 'var(--color-neutral-mid)' }}>DUPLICATES FLAGGED</div>
                      </div>
                      <div style={{ backgroundColor: '#FFF', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                        <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--color-semantic-red)' }}>{csvPreview.missing}</div>
                        <div style={{ fontSize: '10px', color: 'var(--color-neutral-mid)' }}>MISSING FIELDS</div>
                      </div>
                    </div>
                    <button onClick={handleCommitMigration} className="btn-primary" style={{ width: 'auto', padding: '8px 20px', fontSize: '13px' }}>
                      Import {csvPreview.valid} Students & Go Live
                    </button>
                  </div>
                )}
              </div>

              {/* 2. WhatsApp Export Importer */}
              <div style={{ backgroundColor: '#FFF', padding: '20px', borderRadius: '14px', border: '1px solid var(--color-neutral-light)' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '6px' }}>2 · WhatsApp Group Export → Notices</h3>
                <textarea
                  value={waText}
                  onChange={(e) => setWaText(e.target.value)}
                  placeholder="Paste WhatsApp message: '12/09/26, 10:14 - Warden: Water supply will be off tomorrow 2-4 PM in Hostel B, store water.'"
                  rows={3}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--color-neutral-light)', fontSize: '12px', marginBottom: '12px' }}
                />
                <button onClick={handleConvertWhatsApp} className="btn-primary" style={{ width: 'auto', padding: '8px 20px', fontSize: '13px' }}>
                  Convert to Official Notice
                </button>
              </div>
            </div>
          )}

          {/* ================= TAB 10: ADOPTION PLAN ================= */}
          {currentPage === 'adoption' && (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Institutional Adoption Plan</h1>
                <p style={{ fontSize: '13px', color: 'var(--color-neutral-mid)' }}>
                  Sits on top of existing systems — nothing to rip out (Section 11)
                </p>
              </div>

              <div style={{ backgroundColor: '#FFF', borderRadius: '14px', padding: '20px', border: '1px solid var(--color-neutral-light)', marginBottom: '20px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <tbody>
                    <tr style={{ borderBottom: '1px solid var(--color-neutral-light)' }}>
                      <td style={{ padding: '12px', fontWeight: 700, width: '100px', color: 'var(--color-primary)' }}>Week 0</td>
                      <td style={{ padding: '12px' }}>CSV import of registers, hostel rosters, and fee sheets. Parallel-run with paper.</td>
                    </tr>
                    <tr style={{ borderBottom: '1px solid var(--color-neutral-light)' }}>
                      <td style={{ padding: '12px', fontWeight: 700, color: 'var(--color-primary)' }}>Week 1</td>
                      <td style={{ padding: '12px' }}>Pilot in ONE hostel (Aryabhatta Hall): 2 wardens + 10 student volunteers, SMS fallback on.</td>
                    </tr>
                    <tr style={{ borderBottom: '1px solid var(--color-neutral-light)' }}>
                      <td style={{ padding: '12px', fontWeight: 700, color: 'var(--color-primary)' }}>Week 2</td>
                      <td style={{ padding: '12px' }}>Replace WhatsApp notice groups for CSE department; WhatsApp export importer for archive history.</td>
                    </tr>
                    <tr style={{ borderBottom: '1px solid var(--color-neutral-light)' }}>
                      <td style={{ padding: '12px', fontWeight: 700, color: 'var(--color-primary)' }}>Week 3</td>
                      <td style={{ padding: '12px' }}>Gate pass + mess feedback for all residential hostels; kiosks in common lounges.</td>
                    </tr>
                    <tr style={{ borderBottom: '1px solid var(--color-neutral-light)' }}>
                      <td style={{ padding: '12px', fontWeight: 700, color: 'var(--color-primary)' }}>Week 4</td>
                      <td style={{ padding: '12px' }}>Campus-wide rollout. Attendance connects to the existing biometric system via read-only adapter without replacement.</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div style={{ backgroundColor: '#FFF', padding: '18px', borderRadius: '12px', border: '1px solid var(--color-neutral-light)' }}>
                  <h4 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '6px' }}>Data Needed</h4>
                  <p style={{ fontSize: '12px', color: 'var(--color-neutral-mid)', lineHeight: '1.4' }}>
                    Student roster (name, roll, branch, year, phone, hostel/room) · staff & department mapping · timetable · mess menu · campus 3D GLB.
                  </p>
                </div>
                <div style={{ backgroundColor: '#FFF', padding: '18px', borderRadius: '12px', border: '1px solid var(--color-neutral-light)' }}>
                  <h4 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '6px' }}>Habit Migration</h4>
                  <p style={{ fontSize: '12px', color: 'var(--color-neutral-mid)', lineHeight: '1.4' }}>
                    SMS fallback = nobody excluded. Warden resolution score in monthly reports. Students see live status without queueing.
                  </p>
                </div>
              </div>
            </div>
          )}

        </main>
      </div>

      {/* Floating Assistant Button (matching prototype bottom-right chat bubble) */}
      <button
        onClick={() => setShowVoiceModal(true)}
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          width: '52px',
          height: '52px',
          borderRadius: '50%',
          backgroundColor: 'var(--color-primary)',
          color: '#FFFFFF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--shadow-lg)',
          zIndex: 999,
          border: '2px solid rgba(255,255,255,0.4)'
        }}
      >
        <MessageSquare size={22} />
      </button>
    </div>
  );
}
