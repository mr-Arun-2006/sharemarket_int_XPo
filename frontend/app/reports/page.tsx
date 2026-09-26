"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { apiDownload, apiFetch } from "../../lib/api";

type Report={report_id:string;analysis_id:string;report_type:string;title:string;trade_date:string;language:string;generated_at:string;status:string};

export default function ReportsPage(){
  const [reports,setReports]=useState<Report[]>([]); const [error,setError]=useState(""); const [loading,setLoading]=useState(true);

  async function load(){
    try{setReports((await apiFetch<{reports:Report[]}>("/api/v1/reports?limit=50")).reports);}
    catch(err){setError(err instanceof Error?err.message:"Unable to load reports");}
    finally{setLoading(false);}
  }
  useEffect(()=>{load()},[]);

  async function download(id:string){
    try{
      const blob=await apiDownload("/api/v1/reports/"+encodeURIComponent(id)+"/pdf");
      const url=URL.createObjectURL(blob); const a=document.createElement("a"); a.href=url; a.download=id+".pdf"; a.click(); URL.revokeObjectURL(url);
    }catch(err){setError(err instanceof Error?err.message:"PDF download failed");}
  }

  return <AppShell>
    <section className="page-heading"><div><div className="eyebrow">Reports</div><h1>Research reports</h1><p className="lead">Generate and export professional PDF reports from preserved EOD intelligence analyses.</p></div></section>
    {error&&<div className="error">{error}</div>}
    <section className="panel"><div className="section-title"><div><div className="eyebrow">Report History</div><h2>Generated reports</h2></div><span className="caption">{loading?"Loading...":reports.length+" reports"}</span></div>
      {loading?<div className="empty">Loading reports...</div>:<div className="table-wrap"><table><thead><tr><th>Report</th><th>Type</th><th>Trade Date</th><th>Language</th><th>Generated</th><th>Actions</th></tr></thead><tbody>
        {reports.map(r=><tr key={r.report_id}><td>{r.title}</td><td>{r.report_type}</td><td>{r.trade_date}</td><td>{r.language}</td><td>{new Date(r.generated_at).toLocaleString()}</td><td><Link className="button" href={"/ai/market?analysis="+encodeURIComponent(r.analysis_id)}>Source</Link>{" "}<button className="button" onClick={()=>download(r.report_id)}>PDF</button></td></tr>)}
        {reports.length===0&&<tr><td colSpan={6}>No reports generated yet. Generate an EOD analysis, then use Export PDF.</td></tr>}
      </tbody></table></div>}
    </section>
    <section className="grid-2" style={{marginTop:18}}>
      <article className="panel"><div className="eyebrow">Market</div><h2>EOD Market Reports</h2><p className="muted">Market diagnosis, breadth, regime, movers, evidence and data gaps.</p><Link className="button primary" href="/ai/market">Generate from AI workspace</Link></article>
      <article className="panel"><div className="eyebrow">Stock</div><h2>Stock Reports</h2><p className="muted">Selected-stock technical context plus evidence and explicit missing-data sections.</p><Link className="button" href="/stocks">Choose a stock</Link></article>
    </section>
  </AppShell>;
}
