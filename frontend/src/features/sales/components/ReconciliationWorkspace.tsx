"use client";

import React, { useState } from "react";
import { useWorkspace } from "../workspace/useWorkspace";
import { WorkspaceView } from "./WorkspaceView";
import { ReconciliationResultsView } from "./ReconciliationResultsView";
import { AlertTriangle } from "lucide-react";

interface ReconciliationWorkspaceProps {
  type: "sales" | "purchases";
}

type WorkspaceNavigationState = "workspace" | "results";

export function ReconciliationWorkspace({ type }: ReconciliationWorkspaceProps) {
  const [navState, setNavState] = useState<WorkspaceNavigationState>("workspace");

  const {
    fromDate, setFromDate, toDate, setToDate, fileStatuses, fileInputRef,
    uiState, summary, globalError, handleLoadSap, handleLoadErpFile, handleFileUpload, 
    handleCompare: triggerCompare,
    sapPagination, kraPagination, resultsPagination,
    resultsFilter, setResultsFilter, resultStatusCounts,
    workflowStep, readyToCompare, sessionId
  } = useWorkspace(type);

  // We wrap handleCompare to also handle navigation to the Results view
  const handleCompareWithNavigation = async () => {
    const ok = await triggerCompare();
    if (ok) {
      setNavState("results");
    }
  };

  return (
    <div className="flex flex-col gap-3.5 w-full h-full min-h-0 overflow-hidden">
      {/* Shared Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight capitalize">
            {type} Reconciliation
          </h2>
          <p suppressHydrationWarning className="text-xs text-slate-400 mt-0.5">
            SAP ERP ↔ KRA Portal · {new Date().toLocaleDateString("en-KE", { month: "long", year: "numeric" })}
          </p>
        </div>
      </div>

      {globalError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm shadow-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {globalError}
        </div>
      )}

      {navState === "workspace" ? (
        <WorkspaceView
          type={type}
          fromDate={fromDate}
          setFromDate={setFromDate}
          toDate={toDate}
          setToDate={setToDate}
          fileStatuses={fileStatuses}
          fileInputRef={fileInputRef}
          uiState={uiState}
          handleLoadSap={handleLoadSap}
          handleLoadErpFile={handleLoadErpFile}
          handleFileUpload={handleFileUpload}
          handleCompare={handleCompareWithNavigation}
          sapPagination={sapPagination}
          kraPagination={kraPagination}
          workflowStep={workflowStep}
          readyToCompare={readyToCompare}
        />

      ) : (
        <>
          {sessionId ? (
             <ReconciliationResultsView
               sessionId={sessionId}
               type={type}
               summary={summary}
               resultsPagination={resultsPagination}
               comparisonStatus={uiState.comparison.status}
               emptyReason={uiState.comparison.emptyReason}
               resultsFilter={resultsFilter}
               onResultsFilterChange={setResultsFilter}
               resultStatusCounts={resultStatusCounts}
               onBack={() => setNavState("workspace")}
             />
          ) : (
             <div className="bg-white p-10 text-center rounded-lg border border-slate-200 shadow-sm text-slate-500">
               <p>No active session found. Please return to the workspace and load data.</p>
               <button onClick={() => setNavState("workspace")} className="mt-4 text-[#0e1734] hover:text-[#16224c] font-semibold">Return to Workspace</button>
             </div>
          )}
        </>
      )}
    </div>
  );
}
