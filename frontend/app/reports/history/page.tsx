"use client";

import { useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { apiDownload, apiFetch } from "../../../lib/api";

type Report={report_id:string;analysis_id:string;report_type:string;title:string;trade_date:string;language:string;generated_at:string;status:string};

export default function ReportHistoryPage(){
  const [rows,setRows]=useState<Report[]>([]); const [error,setError]=useState("");
  useEffect(()=>{apiFetch<{reports:Report[]}>("/api/v1/reports?limit=100").then(r=>setRows(r.reports)).catch(e=>setError(e instanceof Error?e.message:"Unable to load reports"));},[]);
  async function download(id:string){
    try{const blob=await apiDownload("/api/v1/reports/"+encodeURIComponent(id)+"/pdf");const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=id+".pdf";a.click();URL.revokeObjectURL(url);}catch(e){setError(e instanceof Error?e.message:"PDF download failed");}
  }
  return <AppShell><section className="page-heading"><div><div className="eyebrow">Reports / History</div><h1>Report history</h1><p className="lead">Previously created PDF report records.</p></div></section>{error&&<div className="error">{error}</div>}<section className="panel"><div className="table-wrap"><table><thead><tr><th>Title</th><th>Type</th><th>Trade date</th><th>Language</th><th>Generated</th><th></th></tr></thead><tbody>{rows.map(r=><tr key={r.report_id}><td>{r.title}</td><td>{r.report_type}</td><td>{r.trade_date}</td><td>{r.language}</td><td>{new Date(r.generated_at).toLocaleString()}</td><td><button className="button" onClick={()=>download(r.report_id)}>PDF</button></td></tr>)}</tbody></table></div>{rows.length===0&&<div className="empty">No reports generated yet.</div>}</section></AppShell>;
}
