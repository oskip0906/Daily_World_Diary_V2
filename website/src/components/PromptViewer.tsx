/**
 * Prompt transparency viewer
 * Displays AI agent prompts in collapsible panels for transparency
 */

import { AgentPrompt } from "@/types";
import { CollapsiblePanel } from "./CollapsiblePanel";

interface PromptViewerProps {
  prompts: AgentPrompt[];
}

export function PromptViewer({ prompts }: PromptViewerProps) {
  return (
    <section
      id="prompts"
      className="scroll-mt-8 py-8 border-t-2 border-border dark:border-dark-border mt-12"
    >
      <div className="mb-6">
        <h2 className="text-2xl md:text-3xl font-semibold text-text-primary dark:text-dark-text-primary mb-2">
          Prompt Transparency
        </h2>
        <p className="text-sm text-text-muted dark:text-dark-text-muted">
          View the system prompts used by each AI agent to generate this
          diary entry. These prompts define the agent&apos;s role, constraints,
          and output format.
        </p>
      </div>

      <div className="space-y-3">
        {prompts.map((prompt) => (
          <CollapsiblePanel
            key={prompt.agentId}
            title={prompt.agentName}
            subtitle={`${prompt.description} • v${prompt.version}`}
          >
            <div className="space-y-3">
              <div>
                <h5 className="text-xs font-semibold text-text-muted dark:text-dark-text-muted uppercase tracking-wider mb-2">
                  System Prompt
                </h5>
                <pre className="text-xs text-text-secondary dark:text-dark-text-secondary bg-bg-secondary dark:bg-dark-bg-secondary p-3 rounded overflow-x-auto whitespace-pre-wrap font-mono">
                  {prompt.systemPrompt}
                </pre>
              </div>
              <div className="flex items-center gap-4 text-xs text-text-muted dark:text-dark-text-muted">
                <span>Version: {prompt.version}</span>
                <span>•</span>
                <span>
                  Updated:{" "}
                  {new Date(prompt.lastUpdated).toLocaleDateString()}
                </span>
              </div>
            </div>
          </CollapsiblePanel>
        ))}
      </div>
    </section>
  );
}
