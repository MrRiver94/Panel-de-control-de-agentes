"""One durable mission at a time; each role runs a real, sequential Codex turn."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import json
import logging
import threading

from fastapi import HTTPException

from . import state
from .codex_process import find_codex, login_ready, run_codex, stop_process
from .config import PROJECT_ROOT
from .execution_store import read_executions, save_execution, execution_for_request, save_execution_diffs
from .models import DispatchRequest
from .repository import save_activity_event, save_agent_registry
from .timeutils import now
from .execution_diff import capture_baseline, collect_diffs
from .review import parse_review
from .mission_plan import choose_agents, build_prompt

ACTIVE = {"queued", "running", "cancelling"}
LOGGER = logging.getLogger(__name__)


class ExecutionManager:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.worker: threading.Thread | None = None
        self.process = None
        self.current: dict | None = None
        self.stopping = False

    def recover(self) -> None:
        """Never replay an interrupted mission or revive prototype running states."""
        history = read_executions(10000)
        measured = {}
        for execution in history:
            if execution["status"] in ACTIVE:
                execution.update(status="interrupted", active_agent=None, finished_at=now().isoformat(), error="La API se reinició durante la misión; no se ha relanzado.")
                for step in execution["steps"]:
                    if step["status"] == "queued":
                        step["status"] = "skipped"
                    elif step["status"] in ACTIVE:
                        step["status"] = "interrupted"
                save_execution(execution)
            for step in execution["steps"]:
                if step["agent_id"] not in measured and step["status"] != "skipped":
                    usage = step.get("usage") or {}
                    measured[step["agent_id"]] = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        for agent in state.agents.values():
            agent.status, agent.current_task = "standby", "En espera"
            agent.tokens_used = measured.get(agent.id, 0)
            agent.execution_id = agent.session_id = agent.work_action = None
            agent.usage_source = "codex-exec"
            save_agent_registry(agent)

    def status(self) -> dict:
        executable = find_codex()
        ready, message = login_ready(executable) if executable else (False, "No encuentro Codex CLI. Configura AGENT_CODEX_BIN.")
        return {"ready": ready, "message": message, "workspace": str(PROJECT_ROOT), "engine": "codex-exec", "busy": bool(self.worker and self.worker.is_alive())}

    def start(self, request: DispatchRequest) -> dict:
        with self.lock:
            existing = execution_for_request(request.request_id)
            if existing:
                workspace = str(Path(request.workspace or PROJECT_ROOT).expanduser().resolve())
                if (existing['prompt'], existing['workspace'], existing['sandbox'], existing.get('planning','guided')) != (request.prompt, workspace, request.sandbox, request.planning):
                    raise HTTPException(409, "El identificador de envío ya pertenece a otra misión.")
                return self._accepted(existing)
            if self.stopping or (self.worker and self.worker.is_alive()):
                raise HTTPException(409, "Hay una misión en curso. Espera o cancélala antes de iniciar otra.")
            executable = find_codex()
            if not executable:
                raise HTTPException(503, "No encuentro Codex CLI. Configura AGENT_CODEX_BIN.")
            ready, message = login_ready(executable)
            if not ready:
                raise HTTPException(503, message)
            workspace = Path(request.workspace or PROJECT_ROOT).expanduser()
            if not workspace.is_absolute() or not workspace.is_dir():
                raise HTTPException(400, "El proyecto debe ser una carpeta existente con ruta absoluta.")
            workspace = workspace.resolve()
            if not any((parent / ".git").exists() for parent in (workspace, *workspace.parents)):
                raise HTTPException(400, "Selecciona un proyecto que pertenezca a un repositorio Git.")
            chosen = choose_agents(request.prompt, request.sandbox, request.planning)
            if any(state.agents[key].provider != "codex" for key in chosen):
                raise HTTPException(400, "Esta ejecución utiliza Codex. Cambia a Codex el proveedor de los agentes seleccionados.")
            execution = {
                "id": str(uuid4()), "prompt": request.prompt, "workspace": str(workspace),
                "request_id": request.request_id, "planning": request.planning,
                "sandbox": request.sandbox, "status": "queued", "created_at": now().isoformat(),
                "finished_at": None, "error": None, "active_agent": None,
                "changed_files": [], "outcome": None,
                "steps": [{"agent_id": key, "name": state.agents[key].name, "status": "queued",
                           "model": state.agents[key].model, "effort": state.agents[key].reasoning_effort,
                           "token_budget": state.agents[key].token_budget,
                           "session_id": None, "result": "", "usage": None, "turn_completed": False, "changed_files": []} for key in chosen],
            }
            save_execution(execution)
            self.current, self.cancelled = execution, threading.Event()
            self.worker = threading.Thread(target=self._run, args=(executable, execution), daemon=True)
            self.worker.start()
            return self._accepted(execution)

    @staticmethod
    def _accepted(execution: dict) -> dict:
        return {"execution_id":execution['id'], "agent_ids":[step['agent_id'] for step in execution['steps']],
                "plan":"Misión registrada. Turnos: " + " → ".join(step['name'] for step in execution['steps'])}

    def _agent_state(self, key: str, status: str, detail: str, action: str | None = None) -> None:
        agent = state.agents[key]
        agent.status, agent.current_task, agent.work_action = status, detail[:120], action
        save_agent_registry(agent)

    def _event(self, execution: dict, step: dict, event: dict) -> None:
        kind = event.get("type")
        agent = state.agents[step["agent_id"]]
        if kind == "thread.started":
            step["session_id"] = agent.session_id = event.get("thread_id")
            save_agent_registry(agent)
        elif kind == "turn.started":
            self._agent_state(agent.id, "thinking", "Codex está procesando la misión", "thinking")
        elif kind == "turn.completed":
            step["turn_completed"] = True
            # Cached input is part of input; reasoning is part of output. Never add them twice.
            usage = event.get("usage")
            if isinstance(usage, dict) and "input_tokens" in usage and "output_tokens" in usage:
                measured = {key: max(0, int(usage.get(key) or 0)) for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")}
                previous = step.get("usage") or {key: 0 for key in measured}
                step["usage"] = {key: previous[key] + measured[key] for key in measured}
                agent.tokens_used += measured["input_tokens"] + measured["output_tokens"]
                save_activity_event(agent.id, agent.name, "codex_usage", "Consumo medido por Codex (razonamiento incluido en salida).", measured["input_tokens"], measured["output_tokens"])
                save_agent_registry(agent)
        elif kind == "turn.failed":
            raise RuntimeError("Codex ha marcado el turno como fallido. Revisa la sesión y la configuración del modelo.")
        elif kind in {"item.started", "item.updated", "item.completed"}:
            item = event.get("item") or {}
            item_type = item.get("type")
            actions = {"reasoning": ("thinking", "thinking", "Procesando la misión"),
                       "command_execution": ("running", "typing", "Ejecutando un comando"),
                       "file_change": ("running", "building", "Aplicando cambios en archivos"),
                       "web_search": ("running", "searching", "Consultando fuentes"),
                       "mcp_tool_call": ("running", "analyzing", "Usando una herramienta"),
                       "plan": ("thinking", "planning", "Preparando el plan"),
                       "agent_message": ("running", "writing", "Redactando el resultado")}
            if item_type in actions:
                status, action, detail = actions[item_type]
                self._agent_state(agent.id, status, detail, action)
            if kind == "item.started" and item_type in {"command_execution", "file_change", "web_search", "mcp_tool_call"}:
                save_activity_event(agent.id, agent.name, "codex_" + item_type, actions[item_type][2])
            if kind == "item.completed" and item_type == "agent_message":
                step["result"] = str(item.get("text", ""))[:30000]
        # Do not expose reasoning text, raw tools or command output.
        save_execution(execution)

    def _run(self, executable: str, execution: dict) -> None:
        execution["status"] = "running"
        context: list[str] = []
        active = None
        try:
            for step in execution["steps"]:
                if self.cancelled.is_set():
                    raise InterruptedError("Ejecución cancelada.")
                active = step
                key = step["agent_id"]
                execution["active_agent"], step["status"] = key, "running"
                agent = state.agents[key]
                agent.tokens_used = 0
                agent.session_id = None
                agent.execution_id = execution["id"]
                self._agent_state(key, "running", "Iniciando Codex", "planning")
                save_activity_event(key, agent.name, "mission_dispatched", "Inicio real de Codex: " + execution["id"])
                save_execution(execution)
                prompt = build_prompt(execution, step, context)
                step['prompt_chars'] = len(prompt)
                sandbox = execution["sandbox"] if key == "forge" else "read-only"
                args = [executable, "exec", "--json", "--color", "never", "-C", execution["workspace"],
                        "--sandbox", sandbox, "-c", 'approval_policy="never"',
                        "-c", "model_reasoning_effort=" + json.dumps(step["effort"])]
                if step["model"]:
                    args += ["--model", step["model"]]
                if key == 'sentinel':
                    args += ['--output-schema', str(PROJECT_ROOT/'runtime/schemas/review.json')]
                args.append("-")
                before = capture_baseline(execution["workspace"]) if sandbox == "workspace-write" else None
                try:
                    run_codex(args, prompt, execution["workspace"], self.cancelled,
                              lambda event: self._event(execution, step, event), self._set_process)
                finally:
                    if before is not None:
                        diffs = collect_diffs(execution["workspace"], before)
                        save_execution_diffs(execution['id'], diffs)
                        step["changed_files"] = [item['path'] for item in diffs]
                        execution["changed_files"] = sorted(set(execution["changed_files"]) | set(step["changed_files"]))
                if self.cancelled.is_set():
                    raise InterruptedError("Ejecución cancelada.")
                if not step["turn_completed"]:
                    raise RuntimeError("Codex terminó sin un evento turn.completed; no se considera completado.")
                step["status"] = "completed"
                if key == 'sentinel':
                    step['review'] = parse_review(step['result'])
                context.append(f"{agent.name}: {step['result'][:6000]}")
                self._agent_state(key, "standby", "En espera")
                save_activity_event(key, agent.name, "codex_completed", "Fase finalizada correctamente.")
                save_execution(execution)
            with self.lock:
                if self.cancelled.is_set():
                    raise InterruptedError("Ejecución cancelada.")
                if execution["sandbox"] == "workspace-write" and not execution["changed_files"]:
                    execution["status"] = "no_changes"
                    execution["outcome"] = "Codex terminó sus turnos, pero no se detectaron cambios en los archivos. Revisa la respuesta de FORGE."
                else:
                    review=next((step.get('review') for step in execution['steps'] if step['agent_id']=='sentinel'),None)
                    execution["status"] = 'needs_review' if execution['sandbox']=='workspace-write' and (not review or review['verdict']!='approved') else "completed"
                    execution["outcome"] = ("Cambios generados con observaciones; revisa SENTINEL." if execution['status']=='needs_review' else "Cambios generados y revisados por SENTINEL; comprueba el resultado final." if execution["sandbox"] == "workspace-write" else "Propuesta de solo lectura finalizada; no se han solicitado cambios en archivos.")
        except InterruptedError:
            execution["status"], execution["error"] = "cancelled", "Misión cancelada. Los cambios ya realizados se conservan."
        except Exception as error:
            LOGGER.exception('Fallo en la ejecución %s', execution['id'])
            execution["status"] = "cancelled" if self.cancelled.is_set() else "failed"
            execution["error"] = ("Misión cancelada. Los cambios ya realizados se conservan." if self.cancelled.is_set()
                                  else str(error)[:500] if isinstance(error, RuntimeError)
                                  else "No se pudo ejecutar Codex. Revisa configuración y permisos de la API.")
        finally:
            if active and active["status"] == "running":
                active["status"] = execution["status"]
                key = active["agent_id"]
                self._agent_state(key, "error" if execution["status"] == "failed" else "standby", execution["error"] or "En espera")
                save_activity_event(key, state.agents[key].name, "codex_error" if execution["status"] == "failed" else "codex_cancelled", execution["error"] or "Finalizado")
            for step in execution["steps"]:
                if step["status"] == "queued":
                    step["status"] = "skipped"
            execution.update(active_agent=None, finished_at=now().isoformat())
            save_execution(execution)

    def _set_process(self, process) -> None:
        with self.lock:
            self.process = process

    def cancel(self, execution_id: str) -> None:
        with self.lock:
            if not self.current or self.current["id"] != execution_id or self.current["status"] not in ACTIVE:
                raise HTTPException(409, "La misión ya no está en ejecución.")
            self.cancelled.set()
            self.current["status"] = "cancelling"
            save_execution(self.current)

    def shutdown(self) -> None:
        with self.lock:
            self.stopping = True
            self.cancelled.set()
            process = self.process
        if process:
            stop_process(process)
        if self.worker:
            self.worker.join(timeout=15)


manager = ExecutionManager()
