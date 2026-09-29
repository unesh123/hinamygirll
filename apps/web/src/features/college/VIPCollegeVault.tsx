import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  GraduationCap,
  Terminal,
  BookOpen,
  Video,
  Code,
  Sparkles,
  UserCheck,
  Download,
  Play,
  Search,
  Award,
  Activity,
  Check,
  ExternalLink,
  ChevronRight,
  Lock,
  Unlock,
  AlertCircle,
  Copy,
} from "lucide-react";

export interface VIPResource {
  id: string;
  category: "cybersecurity" | "python_ai_scripts" | "lecture_videos" | "academic_syllabus" | "research_dossiers";
  title: string;
  description: string;
  access_level: "standard_student" | "vip_exclusive" | "faculty_only";
  tags: string[];
  download_url?: string | null;
  content_payload?: string | null;
}

export interface StudentProfile {
  student_id: string;
  full_name: string;
  email: string;
  department: string;
  semester: number;
  role: "student" | "faculty" | "admin";
  vip_access_granted: boolean;
  auth_token?: string;
  registered_at?: string;
  gpa_standing?: string;
}

export interface AdminStats {
  total_enrolled_students: number;
  vip_vault_active_users: number;
  department_breakdown: Record<string, number>;
  resources_in_vault: number;
  system_health: string;
  institutional_tier: string;
}

interface VIPCollegeVaultProps {
  onOpenTerminal?: (initialCommand: string) => void;
  onNavigateHome?: () => void;
}

export function VIPCollegeVault({ onOpenTerminal, onNavigateHome }: VIPCollegeVaultProps) {
  // State
  const [resources, setResources] = useState<VIPResource[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedResource, setSelectedResource] = useState<VIPResource | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Student Profile / Auth State
  const [student, setStudent] = useState<StudentProfile | null>(() => {
    try {
      const saved = localStorage.getItem("hinaa_college_student");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [showRegisterModal, setShowRegisterModal] = useState<boolean>(false);
  const [registerForm, setRegisterForm] = useState({
    student_id: "",
    full_name: "",
    email: "",
    department: "Computer Science & Engineering",
    semester: 4,
    role: "student" as "student" | "faculty" | "admin",
  });
  const [isRegistering, setIsRegistering] = useState<boolean>(false);
  const [registerSuccessMsg, setRegisterSuccessMsg] = useState<string | null>(null);

  // Admin Stats State
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null);
  const [showAdminTab, setShowAdminTab] = useState<boolean>(false);

  // Fetch Resources
  const fetchResources = useCallback(async (cat?: string) => {
    try {
      setLoading(true);
      setError(null);
      const url = cat && cat !== "all" 
        ? `/v1/college/resources?category=${encodeURIComponent(cat)}`
        : "/v1/college/resources";
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load vault resources`);
      const data = await res.json();
      setResources(data.resources || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load resources from College Vault");
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch Admin Stats
  const fetchAdminStats = useCallback(async () => {
    try {
      const res = await fetch("/v1/college/admin/stats");
      if (res.ok) {
        const data = await res.json();
        setAdminStats(data);
      }
    } catch (err) {
      console.error("Failed to fetch admin stats", err);
    }
  }, []);

  useEffect(() => {
    fetchResources(selectedCategory);
    fetchAdminStats();
  }, [selectedCategory, fetchResources, fetchAdminStats]);

  // Handle Registration
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!registerForm.student_id || !registerForm.full_name || !registerForm.email) return;

    setIsRegistering(true);
    try {
      const res = await fetch("/v1/college/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(registerForm),
      });
      if (!res.ok) throw new Error("Registration failed");
      const data = await res.json();
      setStudent(data.student);
      localStorage.setItem("hinaa_college_student", JSON.stringify(data.student));
      setRegisterSuccessMsg(`Welcome, ${data.student.full_name}! Verified for VIP Deep Vault access.`);
      fetchAdminStats();
      setTimeout(() => {
        setShowRegisterModal(false);
        setRegisterSuccessMsg(null);
      }, 1500);
    } catch (err: any) {
      alert(`Registration error: ${err.message}`);
    } finally {
      setIsRegistering(false);
    }
  };

  const handleCopyCode = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Filtered resources
  const filteredResources = resources.filter((item) => {
    if (selectedCategory !== "all" && item.category !== selectedCategory) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = item.title.toLowerCase().includes(q);
      const matchDesc = item.description.toLowerCase().includes(q);
      const matchTags = item.tags.some((t) => t.toLowerCase().includes(q));
      return matchTitle || matchDesc || matchTags;
    }
    return true;
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        width: "100%",
        backgroundColor: "#faf8f5", // Warm paper tone
        color: "#1a1a1a",
        overflowY: "auto",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
      }}
    >
      {/* ── Steep Editorial Header ── */}
      <header
        style={{
          borderBottom: "1px solid #e8e3dc",
          backgroundColor: "#ffffff",
          padding: "24px 36px 20px 36px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                fontSize: 11,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.12em",
                backgroundColor: "#fbe1d1", // Steep warm peach accent
                color: "#833d1c",
                padding: "3px 9px",
                borderRadius: 9999,
              }}
            >
              <ShieldCheck size={13} />
              DIP World & Institutional College Portal
            </span>
            <span style={{ fontSize: 12, color: "#78716c" }}>
              Tier-1 Autonomous Engineering Node
            </span>
          </div>

          <h1
            style={{
              fontFamily: "'Newsreader', 'Signifier', 'Georgia', serif",
              fontSize: 28,
              fontWeight: 500,
              letterSpacing: "-0.02em",
              margin: 0,
              color: "#1c1917",
            }}
          >
            VIP Deep Vault & Academic Curriculum
          </h1>
          <p
            style={{
              margin: "6px 0 0 0",
              fontSize: 14,
              color: "#78716c",
              maxWidth: 680,
              lineHeight: 1.45,
            }}
          >
            Curated repository for verified students and faculty. Access defensive cybersecurity playbooks,
            production Python AI swarm architectures, complete syllabus roadmaps, and 4-hour video lectures.
          </p>
        </div>

        {/* Student Identity Card / Action */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {student ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                backgroundColor: "#f5f3ef",
                border: "1px solid #e8e3dc",
                padding: "8px 14px",
                borderRadius: 10,
              }}
            >
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  backgroundColor: "#1c1917",
                  color: "#ffffff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 600,
                  fontSize: 13,
                }}
              >
                {student.full_name.charAt(0).toUpperCase()}
              </div>
              <div style={{ fontSize: 13 }}>
                <div style={{ fontWeight: 600, color: "#1c1917", display: "flex", alignItems: "center", gap: 6 }}>
                  {student.full_name}
                  <span
                    style={{
                      fontSize: 10,
                      backgroundColor: "#10b981",
                      color: "#ffffff",
                      padding: "1px 6px",
                      borderRadius: 4,
                      fontWeight: 700,
                    }}
                  >
                    VIP
                  </span>
                </div>
                <div style={{ color: "#78716c", fontSize: 11 }}>
                  {student.student_id} · Sem {student.semester} ({student.department.split(" ")[0]})
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowRegisterModal(true)}
                style={{
                  marginLeft: 6,
                  fontSize: 11,
                  padding: "4px 8px",
                  borderRadius: 6,
                  border: "1px solid #d6d0c7",
                  backgroundColor: "#ffffff",
                  cursor: "pointer",
                  color: "#57534e",
                }}
              >
                Change
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowRegisterModal(true)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                backgroundColor: "#1c1917",
                color: "#ffffff",
                border: "none",
                borderRadius: 8,
                padding: "10px 18px",
                fontWeight: 600,
                fontSize: 13,
                cursor: "pointer",
                boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
              }}
            >
              <GraduationCap size={16} />
              Verify Student ID for VIP Access
            </button>
          )}

          {onOpenTerminal && (
            <button
              type="button"
              onClick={() => onOpenTerminal("git status")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                backgroundColor: "#ffffff",
                color: "#1c1917",
                border: "1px solid #e8e3dc",
                borderRadius: 8,
                padding: "10px 14px",
                fontWeight: 600,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              <Terminal size={15} />
              Terminal Hands
            </button>
          )}
        </div>
      </header>

      {/* ── Main Workspace Body ── */}
      <div style={{ padding: "24px 36px", flex: 1 }}>
        {/* Navigation & Controls Bar */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 16,
            marginBottom: 24,
          }}
        >
          {/* Category Tabs */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {[
              { id: "all", label: "All Vault Artifacts", icon: BookOpen },
              { id: "cybersecurity", label: "Defensive Security & Pentesting", icon: ShieldCheck },
              { id: "python_ai_scripts", label: "Python AI & Agent Swarms", icon: Code },
              { id: "lecture_videos", label: "4-Hour Video Masterclasses", icon: Video },
              { id: "academic_syllabus", label: "College Syllabus & Roadmap", icon: GraduationCap },
            ].map((tab) => {
              const Icon = tab.icon;
              const isSelected = selectedCategory === tab.id && !showAdminTab;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => {
                    setSelectedCategory(tab.id);
                    setShowAdminTab(false);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "7px 14px",
                    borderRadius: 8,
                    fontSize: 13,
                    fontWeight: isSelected ? 600 : 500,
                    cursor: "pointer",
                    border: isSelected ? "1px solid #1c1917" : "1px solid #e8e3dc",
                    backgroundColor: isSelected ? "#1c1917" : "#ffffff",
                    color: isSelected ? "#ffffff" : "#44403c",
                    transition: "all 0.15s ease",
                  }}
                >
                  <Icon size={14} />
                  {tab.label}
                </button>
              );
            })}

            <button
              type="button"
              onClick={() => setShowAdminTab(true)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "7px 14px",
                borderRadius: 8,
                fontSize: 13,
                fontWeight: showAdminTab ? 600 : 500,
                cursor: "pointer",
                border: showAdminTab ? "1px solid #1c1917" : "1px solid #e8e3dc",
                backgroundColor: showAdminTab ? "#1c1917" : "#ffffff",
                color: showAdminTab ? "#ffffff" : "#78716c",
              }}
            >
              <Activity size={14} />
              Dean & Faculty Analytics
            </button>
          </div>

          {/* Search Box */}
          {!showAdminTab && (
            <div
              style={{
                position: "relative",
                width: 280,
              }}
            >
              <Search
                size={15}
                style={{
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "#a8a29e",
                }}
              />
              <input
                type="text"
                placeholder="Search dossiers, scripts, tags..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px 8px 36px",
                  borderRadius: 8,
                  border: "1px solid #e8e3dc",
                  backgroundColor: "#ffffff",
                  fontSize: 13,
                  outline: "none",
                  boxSizing: "border-box",
                  color: "#1c1917",
                }}
              />
            </div>
          )}
        </div>

        {/* ── Content View ── */}
        {showAdminTab ? (
          /* Dean / Admin Analytics View */
          <div
            style={{
              backgroundColor: "#ffffff",
              borderRadius: 12,
              border: "1px solid #e8e3dc",
              padding: 28,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
              <Award size={22} style={{ color: "#d97706" }} />
              <div>
                <h2
                  style={{
                    fontFamily: "'Newsreader', 'Signifier', 'Georgia', serif",
                    margin: 0,
                    fontSize: 20,
                  }}
                >
                  Institutional Dean & Faculty Oversight
                </h2>
                <p style={{ margin: "2px 0 0 0", fontSize: 13, color: "#78716c" }}>
                  Real-time telemetry of student cohort access, course progression, and vault integrity.
                </p>
              </div>
            </div>

            {adminStats ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
                <div
                  style={{
                    padding: 16,
                    borderRadius: 10,
                    backgroundColor: "#faf8f5",
                    border: "1px solid #e8e3dc",
                  }}
                >
                  <div style={{ fontSize: 12, color: "#78716c", fontWeight: 600 }}>Enrolled Students</div>
                  <div
                    style={{
                      fontSize: 28,
                      fontWeight: 700,
                      color: "#1c1917",
                      marginTop: 4,
                      fontFamily: "'Newsreader', 'Signifier', serif",
                    }}
                  >
                    {adminStats.total_enrolled_students}
                  </div>
                  <div style={{ fontSize: 11, color: "#16a34a", marginTop: 4 }}>100% active cohort verification</div>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 10,
                    backgroundColor: "#faf8f5",
                    border: "1px solid #e8e3dc",
                  }}
                >
                  <div style={{ fontSize: 12, color: "#78716c", fontWeight: 600 }}>VIP Vault Resources</div>
                  <div
                    style={{
                      fontSize: 28,
                      fontWeight: 700,
                      color: "#1c1917",
                      marginTop: 4,
                      fontFamily: "'Newsreader', 'Signifier', serif",
                    }}
                  >
                    {adminStats.resources_in_vault}
                  </div>
                  <div style={{ fontSize: 11, color: "#78716c", marginTop: 4 }}>Curated syllabi & playbooks</div>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 10,
                    backgroundColor: "#faf8f5",
                    border: "1px solid #e8e3dc",
                  }}
                >
                  <div style={{ fontSize: 12, color: "#78716c", fontWeight: 600 }}>Vault Security Invariant</div>
                  <div
                    style={{
                      fontSize: 16,
                      fontWeight: 600,
                      color: "#16a34a",
                      marginTop: 8,
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <ShieldCheck size={18} />
                    Verified & Encrypted
                  </div>
                  <div style={{ fontSize: 11, color: "#78716c", marginTop: 6 }}>
                    PBKDF2 & SHA256 Identity Proofs
                  </div>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 10,
                    backgroundColor: "#faf8f5",
                    border: "1px solid #e8e3dc",
                  }}
                >
                  <div style={{ fontSize: 12, color: "#78716c", fontWeight: 600 }}>Institutional Edition</div>
                  <div
                    style={{
                      fontSize: 15,
                      fontWeight: 600,
                      color: "#1c1917",
                      marginTop: 8,
                    }}
                  >
                    {adminStats.institutional_tier}
                  </div>
                  <div style={{ fontSize: 11, color: "#78716c", marginTop: 6 }}>Nepal & Global College Network</div>
                </div>
              </div>
            ) : (
              <div style={{ color: "#78716c", fontSize: 13 }}>Loading dean telemetry…</div>
            )}
          </div>
        ) : loading ? (
          <div style={{ padding: 48, textAlign: "center", color: "#78716c" }}>
            <Sparkles size={24} style={{ animation: "spin 2s linear infinite", marginBottom: 12 }} />
            <div>Accessing VIP Deep Vault…</div>
          </div>
        ) : error ? (
          <div
            style={{
              padding: 24,
              backgroundColor: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: 10,
              color: "#991b1b",
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <AlertCircle size={20} />
            <div>{error}</div>
          </div>
        ) : filteredResources.length === 0 ? (
          <div
            style={{
              padding: 48,
              textAlign: "center",
              backgroundColor: "#ffffff",
              borderRadius: 12,
              border: "1px solid #e8e3dc",
              color: "#78716c",
            }}
          >
            No artifacts found matching query.
          </div>
        ) : (
          /* Grid of VIP Resources */
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
              gap: 20,
            }}
          >
            {filteredResources.map((item) => {
              const isVip = item.access_level === "vip_exclusive";
              return (
                <div
                  key={item.id}
                  style={{
                    backgroundColor: "#ffffff",
                    borderRadius: 12,
                    border: "1px solid #e8e3dc",
                    padding: 20,
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    transition: "transform 0.15s ease, box-shadow 0.15s ease",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
                  }}
                >
                  <div>
                    {/* Header Tags */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.08em",
                          backgroundColor: "#f5f3ef",
                          color: "#57534e",
                          padding: "2px 8px",
                          borderRadius: 4,
                        }}
                      >
                        {item.category.replace(/_/g, " ")}
                      </span>

                      {isVip ? (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            fontSize: 10,
                            fontWeight: 700,
                            backgroundColor: "#fbe1d1", // Steep peach
                            color: "#833d1c",
                            padding: "2px 8px",
                            borderRadius: 9999,
                          }}
                        >
                          <Lock size={10} />
                          VIP Exclusive
                        </span>
                      ) : (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            fontSize: 10,
                            fontWeight: 700,
                            backgroundColor: "#e0f2fe",
                            color: "#0369a1",
                            padding: "2px 8px",
                            borderRadius: 9999,
                          }}
                        >
                          <Unlock size={10} />
                          Standard Access
                        </span>
                      )}
                    </div>

                    {/* Title */}
                    <h3
                      style={{
                        fontFamily: "'Newsreader', 'Signifier', 'Georgia', serif",
                        fontSize: 18,
                        fontWeight: 600,
                        margin: "0 0 8px 0",
                        color: "#1c1917",
                        lineHeight: 1.3,
                      }}
                    >
                      {item.title}
                    </h3>

                    {/* Description */}
                    <p
                      style={{
                        fontSize: 13,
                        color: "#57534e",
                        margin: "0 0 16px 0",
                        lineHeight: 1.45,
                      }}
                    >
                      {item.description}
                    </p>

                    {/* Tag Pills */}
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 20 }}>
                      {item.tags.map((tag) => (
                        <span
                          key={tag}
                          style={{
                            fontSize: 11,
                            backgroundColor: "#f5f3ef",
                            color: "#78716c",
                            padding: "2px 7px",
                            borderRadius: 4,
                          }}
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Action Bar */}
                  <div
                    style={{
                      borderTop: "1px solid #f5f3ef",
                      paddingTop: 14,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => setSelectedResource(item)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        backgroundColor: "#1c1917",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: 6,
                        padding: "7px 14px",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      <BookOpen size={13} />
                      Inspect Dossier
                    </button>

                    {item.content_payload && onOpenTerminal && (
                      <button
                        type="button"
                        onClick={() => {
                          const cmd = item.category === "cybersecurity" 
                            ? "pytest apps/api/tests -k security" 
                            : "python -c \"print('Executing VIP deep payload in sandbox...')\"";
                          onOpenTerminal(cmd);
                        }}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 5,
                          backgroundColor: "#f5f3ef",
                          color: "#1c1917",
                          border: "1px solid #e8e3dc",
                          borderRadius: 6,
                          padding: "7px 12px",
                          fontSize: 12,
                          fontWeight: 500,
                          cursor: "pointer",
                        }}
                      >
                        <Play size={12} />
                        Run in Sandbox
                      </button>
                    )}

                    {item.download_url && (
                      <a
                        href={item.download_url}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                          fontSize: 12,
                          color: "#0369a1",
                          textDecoration: "none",
                          fontWeight: 600,
                        }}
                      >
                        <Download size={13} />
                        Download
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Modal: Dossier Inspector ── */}
      {selectedResource && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            backdropFilter: "blur(2px)",
          }}
          onClick={() => setSelectedResource(null)}
        >
          <div
            style={{
              backgroundColor: "#ffffff",
              borderRadius: 14,
              border: "1px solid #e8e3dc",
              width: "90%",
              maxWidth: 720,
              maxHeight: "85vh",
              overflowY: "auto",
              padding: 30,
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
              <div>
                <span
                  style={{
                    fontSize: 11,
                    textTransform: "uppercase",
                    backgroundColor: "#fbe1d1",
                    color: "#833d1c",
                    padding: "3px 8px",
                    borderRadius: 4,
                    fontWeight: 700,
                  }}
                >
                  {selectedResource.category.replace(/_/g, " ")}
                </span>
                <h2
                  style={{
                    fontFamily: "'Newsreader', 'Signifier', 'Georgia', serif",
                    margin: "8px 0 4px 0",
                    fontSize: 22,
                    color: "#1c1917",
                  }}
                >
                  {selectedResource.title}
                </h2>
                <div style={{ fontSize: 13, color: "#78716c" }}>{selectedResource.description}</div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedResource(null)}
                style={{
                  border: "none",
                  backgroundColor: "transparent",
                  fontSize: 18,
                  cursor: "pointer",
                  color: "#78716c",
                }}
              >
                ✕
              </button>
            </div>

            {selectedResource.content_payload && (
              <div style={{ marginTop: 20 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    backgroundColor: "#1c1917",
                    color: "#ffffff",
                    padding: "8px 14px",
                    borderTopLeftRadius: 8,
                    borderTopRightRadius: 8,
                    fontSize: 12,
                  }}
                >
                  <span>Executable Artifact & Code Snippets</span>
                  <button
                    type="button"
                    onClick={() => handleCopyCode(selectedResource.content_payload!, selectedResource.id)}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "#a8a29e",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      fontSize: 12,
                    }}
                  >
                    {copiedId === selectedResource.id ? <Check size={13} color="#4ade80" /> : <Copy size={13} />}
                    {copiedId === selectedResource.id ? "Copied" : "Copy Payload"}
                  </button>
                </div>
                <pre
                  style={{
                    margin: 0,
                    padding: 16,
                    backgroundColor: "#0c0a09",
                    color: "#e7e5e4",
                    fontSize: 12,
                    lineHeight: 1.5,
                    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                    borderBottomLeftRadius: 8,
                    borderBottomRightRadius: 8,
                    overflowX: "auto",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {selectedResource.content_payload}
                </pre>

                {onOpenTerminal && (
                  <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
                    <button
                      type="button"
                      onClick={() => {
                        const cmd = selectedResource.category === "cybersecurity"
                          ? "nmap -sn 127.0.0.1"
                          : "python -c \"import sys; print('Hina VIP AI Agent Swarm Initialized')\"";
                        setSelectedResource(null);
                        onOpenTerminal(cmd);
                      }}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        backgroundColor: "#1c1917",
                        color: "#ffffff",
                        padding: "8px 16px",
                        borderRadius: 6,
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: "pointer",
                        border: "none",
                      }}
                    >
                      <Terminal size={14} />
                      Launch in Terminal Hands Sandbox
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Modal: Student Verification / Registration ── */}
      {showRegisterModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            backdropFilter: "blur(2px)",
          }}
          onClick={() => setShowRegisterModal(false)}
        >
          <div
            style={{
              backgroundColor: "#ffffff",
              borderRadius: 14,
              border: "1px solid #e8e3dc",
              width: "90%",
              maxWidth: 480,
              padding: 28,
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <GraduationCap size={20} color="#1c1917" />
                <h3
                  style={{
                    fontFamily: "'Newsreader', 'Signifier', 'Georgia', serif",
                    margin: 0,
                    fontSize: 20,
                  }}
                >
                  Verify Student ID
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowRegisterModal(false)}
                style={{ border: "none", background: "transparent", fontSize: 16, cursor: "pointer" }}
              >
                ✕
              </button>
            </div>

            <p style={{ fontSize: 13, color: "#78716c", margin: "0 0 20px 0", lineHeight: 1.4 }}>
              Enter your college or university credentials to unlock VIP Deep Vault access and link your academic cohort.
            </p>

            {registerSuccessMsg ? (
              <div
                style={{
                  padding: 16,
                  backgroundColor: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  borderRadius: 8,
                  color: "#166534",
                  fontSize: 13,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <Check size={16} />
                {registerSuccessMsg}
              </div>
            ) : (
              <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#44403c", display: "block", marginBottom: 4 }}>
                    University / College Student ID
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. STU-2024-8891"
                    value={registerForm.student_id}
                    onChange={(e) => setRegisterForm({ ...registerForm, student_id: e.target.value })}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: 6,
                      border: "1px solid #d6d0c7",
                      fontSize: 13,
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#44403c", display: "block", marginBottom: 4 }}>
                    Full Student Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Unesh Khatri"
                    value={registerForm.full_name}
                    onChange={(e) => setRegisterForm({ ...registerForm, full_name: e.target.value })}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: 6,
                      border: "1px solid #d6d0c7",
                      fontSize: 13,
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "#44403c", display: "block", marginBottom: 4 }}>
                    Institutional Email
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="student@college.edu.np"
                    value={registerForm.email}
                    onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: 6,
                      border: "1px solid #d6d0c7",
                      fontSize: 13,
                      boxSizing: "border-box",
                    }}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: "#44403c", display: "block", marginBottom: 4 }}>
                      Department
                    </label>
                    <select
                      value={registerForm.department}
                      onChange={(e) => setRegisterForm({ ...registerForm, department: e.target.value })}
                      style={{
                        width: "100%",
                        padding: "8px 10px",
                        borderRadius: 6,
                        border: "1px solid #d6d0c7",
                        fontSize: 13,
                        boxSizing: "border-box",
                        backgroundColor: "#ffffff",
                      }}
                    >
                      <option value="Computer Science & Engineering">CSE / AI</option>
                      <option value="Information Technology">Information Technology</option>
                      <option value="Software Engineering">Software Engineering</option>
                      <option value="Cybersecurity">Cybersecurity</option>
                    </select>
                  </div>

                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: "#44403c", display: "block", marginBottom: 4 }}>
                      Semester (1-8)
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={8}
                      value={registerForm.semester}
                      onChange={(e) => setRegisterForm({ ...registerForm, semester: parseInt(e.target.value) || 1 })}
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: 6,
                        border: "1px solid #d6d0c7",
                        fontSize: 13,
                        boxSizing: "border-box",
                      }}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isRegistering}
                  style={{
                    marginTop: 10,
                    backgroundColor: "#1c1917",
                    color: "#ffffff",
                    padding: "10px",
                    borderRadius: 8,
                    fontWeight: 600,
                    fontSize: 13,
                    border: "none",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6,
                  }}
                >
                  <UserCheck size={16} />
                  {isRegistering ? "Verifying with Dean Database…" : "Complete Verification & Grant VIP Access"}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
