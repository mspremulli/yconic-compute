import streamlit as st
import asyncio
import os
import threading
from swarm.orchestrator import SwarmOrchestrator
from swarm.types.task import TaskType

st.set_page_config(page_title="Yconic Agent Swarm", page_icon="🧠")

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = None

if "results" not in st.session_state:
    st.session_state.results = {}

if "initialized" not in st.session_state:
    st.session_state.initialized = False

if "async_runner" not in st.session_state:
    st.session_state.async_runner = None


class AsyncRunner:
    """Helper to run async code in a dedicated thread with persistent event loop"""
    def __init__(self):
        self.loop = None
        self.thread = None
        self.initialized = False
        
    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        
    def start(self):
        if not self.initialized:
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            self.initialized = True
            import time
            time.sleep(0.5)  # Wait for loop to start
            
    def run(self, coro):
        if not self.initialized:
            self.start()
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=300)


st.title("🧠 Yconic Agent Swarm")

with st.sidebar:
    st.header("Configuration")
    config_path = st.text_input("Config Path", value="./config/agents-fast.yaml")
    
    if st.button("Initialize Swarm", type="primary"):
        with st.spinner("Initializing swarm (this may take a minute)..."):
            try:
                os.chdir("/home/yconic/Desktop/yconic_compute")
                st.session_state.async_runner = AsyncRunner()
                st.session_state.async_runner.start()
                
                st.session_state.orchestrator = SwarmOrchestrator.from_config(config_path)
                st.session_state.async_runner.run(st.session_state.orchestrator.initialize())
                st.session_state.initialized = True
                st.success("Swarm initialized!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    st.divider()
    st.subheader("Agents")
    if st.session_state.orchestrator:
        for name, agent in st.session_state.orchestrator.agents.items():
            st.text(f"• {name}: {agent.role} ({agent.state.value})")

if st.session_state.initialized:
    task_type = st.selectbox(
        "Task Type",
        ["general", "code", "research", "analysis", "creative"],
        index=0
    )

    task_type_map = {
        "general": TaskType.GENERAL,
        "code": TaskType.CODE,
        "research": TaskType.RESEARCH,
        "analysis": TaskType.ANALYSIS,
        "creative": TaskType.CREATIVE,
    }

    task_description = st.text_area("Task Description", height=120, placeholder="What would you like the swarm to do?")

    if st.button("Submit Task", type="primary"):
        if task_description:
            with st.spinner("Swarm is working... (may take 10-30s)"):
                try:
                    runner = st.session_state.async_runner
                    task_id = runner.run(
                        st.session_state.orchestrator.receive_task(
                            task_description, 
                            task_type_map[task_type]
                        )
                    )
                    result = runner.run(st.session_state.orchestrator.execute(task_id))
                    st.session_state.results[task_id] = result
                    
                    st.success("✅ Task completed!")
                    st.subheader("Result")
                    st.write(result.final_answer or result.error)
                    st.info(f"Execution time: {result.execution_time_seconds:.2f}s | Success: {result.success}")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.warning("Please enter a task description")

    if st.session_state.results:
        st.divider()
        st.subheader("📜 History")
        for tid, res in list(st.session_state.results.items())[-5:][::-1]:
            with st.expander(f"Task: {tid[:8]}... ({res.execution_time_seconds:.1f}s)"):
                st.write(res.final_answer or res.error)
else:
    st.info("👈 Click **Initialize Swarm** in the sidebar to get started!")
