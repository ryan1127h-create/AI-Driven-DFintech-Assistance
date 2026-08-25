import { useState } from "react";
import {
  Plus, FileText, Edit3, Trash2, History,
  ArrowLeft, Upload, Archive,
  BookOpen, X, Search,
} from "lucide-react";
import {
  knowledgeBase as initialKB, kbCategories,
} from "../../../data/mock";
import { Card, Badge } from "../../ui";
import { PageHeader, StatusBadge } from "../../student/PageParts";
import { cn } from "../../../utils/cn";

// ============ KNOWLEDGE BASE WITH DOCUMENT MANAGEMENT ============

export function KnowledgeBasePage() {
  const [docs, setDocs] = useState(initialKB);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [showUpload, setShowUpload] = useState(false);
  const [activeCategory, setActiveCategory] = useState("All");
  const [search, setSearch] = useState("");

  const filtered = docs.filter((d) => {
    const matchCat = activeCategory === "All" || d.category === activeCategory;
    const matchSearch = !search || d.title.toLowerCase().includes(search.toLowerCase());
    return matchCat && matchSearch;
  });

  if (selectedDoc) {
    const doc = docs.find((d) => d.id === selectedDoc) || selectedDoc;
    const handleArchive = () => {
      setDocs((prev) => prev.map((d) => d.id === doc.id ? { ...d, status: "archived" } : d));
      setSelectedDoc({ ...doc, status: "archived" });
    };
    const handleDelete = () => {
      setDocs((prev) => prev.filter((d) => d.id !== doc.id));
      setSelectedDoc(null);
    };

    return (
      <div>
        <button onClick={() => setSelectedDoc(null)} className="btn-ghost mb-4 text-xs">
          <ArrowLeft size={14} /> Back to Knowledge Base
        </button>
        <Card className="mb-4">
          <div className="flex items-start justify-between mb-3">
            <div>
              <h2 className="font-display text-lg font-bold text-app-primary">{doc.title}</h2>
              <p className="text-sm text-app-muted">{doc.category} · by {doc.author}</p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={doc.status} />
            </div>
          </div>
          <div className="flex gap-2">
            <button className="btn-outline text-xs"><Edit3 size={12} /> Edit</button>
            <button className="btn-outline text-xs"><Upload size={12} /> Replace</button>
            <button onClick={handleArchive} className="btn-outline text-xs"><Archive size={12} /> Archive</button>
            <button onClick={handleDelete} className="btn-outline text-xs text-red-400"><Trash2 size={12} /> Delete</button>
          </div>
        </Card>

        {/* Version Control */}
        <Card className="mb-4">
          <h3 className="font-display text-base font-semibold text-app-primary mb-3">Version History</h3>
          <div className="space-y-2">
            {doc.versions.map((v, i) => (
              <div key={i} className="rounded-lg p-3 bg-app-hover border border-app-soft">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <Badge color="brand">v{v.version}</Badge>
                    <span className="text-sm text-app-primary">{v.notes}</span>
                  </div>
                  <span className="text-xs text-app-faint">{v.date}</span>
                </div>
                <p className="text-xs text-app-muted">Updated by {v.updatedBy}</p>
              </div>
            ))}
          </div>
        </Card>

        {/* Analytics */}
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-3">Analytics</h3>
          <div className="grid sm:grid-cols-4 gap-3">
            <div className="rounded-lg p-3 bg-app-hover text-center">
              <p className="text-2xl font-display font-bold text-app-primary">{doc.analytics.usageCount}</p>
              <p className="text-xs text-app-muted">Usage Count</p>
            </div>
            <div className="rounded-lg p-3 bg-app-hover text-center">
              <p className="text-sm font-medium text-app-primary">{doc.analytics.lastAccessed}</p>
              <p className="text-xs text-app-muted">Last Accessed</p>
            </div>
            <div className="rounded-lg p-3 bg-app-hover text-center">
              <p className="text-2xl font-display font-bold text-app-primary">{doc.analytics.relatedQuestions}</p>
              <p className="text-xs text-app-muted">Related Questions</p>
            </div>
            <div className="rounded-lg p-3 bg-app-hover text-center">
              <p className={cn("text-2xl font-display font-bold", doc.analytics.confidencePerf > 0.9 ? "text-emerald2-400" : "text-amber-300")}>{Math.round(doc.analytics.confidencePerf * 100)}%</p>
              <p className="text-xs text-app-muted">Confidence Performance</p>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        icon={BookOpen}
        title="Knowledge Base"
        subtitle="Manage chatbot knowledge articles"
        action={<button onClick={() => setShowUpload(!showUpload)} className="btn-primary text-xs"><Plus size={14} /> Upload Document</button>}
      />

      {showUpload && (
        <Card className="mb-4 border-dashed border-app-input">
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-300 mb-3">
              <Upload size={24} />
            </div>
            <p className="font-medium text-app-primary">Upload knowledge document</p>
            <p className="text-sm text-app-muted mt-1">PDF or DOCX · Max 10MB</p>
            <div className="flex gap-2 mt-4">
              <button className="btn-outline text-xs"><FileText size={12} /> Choose PDF</button>
              <button className="btn-outline text-xs"><FileText size={12} /> Choose DOCX</button>
              <button onClick={() => setShowUpload(false)} className="btn-ghost text-xs"><X size={12} /> Cancel</button>
            </div>
          </div>
        </Card>
      )}

      <div className="flex flex-wrap gap-2 mb-4">
        {["All", ...kbCategories].map((c) => (
          <button key={c} onClick={() => setActiveCategory(c)} className={cn("chip border transition", activeCategory === c ? "border-brand-400/30 text-brand-300 bg-brand-500/10" : "border-app-input text-app-secondary hover:border-brand-400/30 hover:text-brand-300")}>{c}</button>
        ))}
      </div>

      <Card className="mb-4 flex items-center gap-2">
        <Search size={16} className="text-app-faint" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search articles..." className="flex-1 bg-transparent text-sm text-app-primary placeholder:text-app-faint focus:outline-none" />
      </Card>

      <div className="space-y-2">
        {filtered.map((kb) => (
          <Card key={kb.id} className="flex items-center gap-3 cursor-pointer hover:border-brand-400/20 transition" >
            <div onClick={() => setSelectedDoc(kb)} className="flex items-center gap-3 flex-1">
              <FileText size={16} className="text-app-muted flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-app-primary truncate">{kb.title}</p>
                <p className="text-xs text-app-faint">{kb.category} · v{kb.versions[0].version} · Updated {kb.versions[0].date} by {kb.versions[0].updatedBy}</p>
              </div>
              <StatusBadge status={kb.status} />
              <div className="flex items-center gap-3 text-xs text-app-faint">
                <span>{kb.analytics.usageCount} uses</span>
                <span>{Math.round(kb.analytics.confidencePerf * 100)}% conf</span>
              </div>
            </div>
            <div className="flex gap-1 border-l border-app-subtle pl-3">
              <button className="p-1.5 rounded-lg text-app-muted hover:text-brand-300 hover:bg-app-hover transition"><Edit3 size={14} /></button>
              <button onClick={() => setSelectedDoc(kb)} className="p-1.5 rounded-lg text-app-muted hover:text-royal-300 hover:bg-app-hover transition"><History size={14} /></button>
              <button className="p-1.5 rounded-lg text-app-muted hover:text-red-400 hover:bg-app-hover transition"><Trash2 size={14} /></button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
