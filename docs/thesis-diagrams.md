# Biểu đồ Kiến trúc Hệ thống - Khóa luận Tốt nghiệp

## 5. Kiến trúc tổng thể của hệ thống

### 5.1 Kiến trúc triển khai hệ thống (Deployment Architecture)

```mermaid
graph TB
    subgraph "Client Layer"
        UI[Web Interface<br/>Streamlit App]
        API[API Client<br/>REST/JSON]
    end

    subgraph "Application Layer"
        direction TB
        OCR[OCR Service<br/>:8001]
        AGENT[Agent Service<br/>:8003]
    end

    subgraph "Infrastructure Layer"
        direction TB
        MONGO[(MongoDB<br/>Document Store<br/>:27017)]
        REDIS[(Redis<br/>Session State<br/>:6379)]
        MILVUS[(Milvus<br/>Vector DB<br/>:19530)]
        LANGFUSE[Langfuse<br/>Observability<br/>:3000]
    end

    subgraph "External Services"
        GEMINI[Google Gemini API<br/>LLM + Vision]
        OPENAI[OpenAI API<br/>Optional LLM]
    end

    UI -->|HTTP/SSE| API
    API -->|OCR Request| OCR
    API -->|Workflow Start| AGENT

    OCR -->|Extracted Text| AGENT
    AGENT -->|State Persistence| MONGO
    AGENT -->|Session Mapping| REDIS
    AGENT -->|Vector Search| MILVUS
    AGENT -->|Traces/Metrics| LANGFUSE

    OCR -->|Vision API| GEMINI
    AGENT -->|LLM Calls| GEMINI
    AGENT -->|Optional| OPENAI

    style UI fill:#e1f5ff
    style OCR fill:#fff4e1
    style AGENT fill:#e8f5e9
    style MONGO fill:#f3e5f5
    style REDIS fill:#fce4ec
    style MILVUS fill:#e0f2f1
    style LANGFUSE fill:#fff9c4
    style GEMINI fill:#e3f2fd
    style OPENAI fill:#e3f2fd
```

### 5.2 Biểu đồ thành phần chức năng (Component Diagram)

```mermaid
graph TB
    subgraph "Frontend Interface"
        WEBUI[WebUI Component<br/>Streamlit]
        UPLOAD[Upload Handler]
        DASHBOARD[Dashboard Component]
        REVIEW[Review Panel]
    end

    subgraph "API Gateway"
        ROUTER[API Router<br/>FastAPI]
        SSE[SSE Stream Handler]
    end

    subgraph "Workflow Engine"
        GRAPH[LangGraph<br/>StateGraph]
        CHECKPOINT[Checkpoint Manager<br/>MongoDB]
    end

    subgraph "Agent Nodes"
        COMP_NODE[Completeness Check Node]
        QUAL_NODE[Quality Check Node]
        DEC_NODE[Final Decision Node]
        HUMAN_NODE[Human Review Node]
        AGENT_REVIEW[Agent Review Node]
    end

    subgraph "Agent Factories"
        COMP_FACTORY[CompletenessAgentFactory]
        QUAL_FACTORY[QualityAgentFactory]
        DEC_FACTORY[DecisionAgentFactory]
        VERIFIER[VerifierAgentFactory]
    end

    subgraph "Tool System"
        SKILL_LOADER[Skill Loader]
        TOOL_REGISTRY[Tool Registry]
        SHARED_TOOLS[Shared Tools<br/>classify-benefit]
        COMP_TOOLS[Completeness Tools]
        QUAL_TOOLS[Quality Tools]
    end

    subgraph "Data Layer"
        MONGO_DB[MongoDB Client]
        REDIS_CLIENT[Redis Client]
        MILVUS_CLIENT[Milvus Client]
    end

    subgraph "External Services"
        LLM_CLIENT[LLM Client<br/>Gemini/OpenAI]
        OCR_CLIENT[OCR Client]
    end

    WEBUI --> UPLOAD
    WEBUI --> DASHBOARD
    WEBUI --> REVIEW
    UPLOAD -->|POST /upload| ROUTER
    DASHBOARD -->|GET /status| ROUTER
    REVIEW -->|POST /resume| ROUTER

    ROUTER --> SSE
    ROUTER --> GRAPH

    GRAPH --> CHECKPOINT
    CHECKPOINT --> MONGO_DB

    GRAPH --> COMP_NODE
    GRAPH --> QUAL_NODE
    GRAPH --> DEC_NODE
    GRAPH --> HUMAN_NODE
    GRAPH --> AGENT_REVIEW

    COMP_NODE --> COMP_FACTORY
    QUAL_NODE --> QUAL_FACTORY
    DEC_NODE --> DEC_FACTORY
    AGENT_REVIEW --> VERIFIER

    COMP_FACTORY --> SKILL_LOADER
    QUAL_FACTORY --> SKILL_LOADER
    DEC_FACTORY --> SKILL_LOADER

    SKILL_LOADER --> TOOL_REGISTRY
    TOOL_REGISTRY --> SHARED_TOOLS
    TOOL_REGISTRY --> COMP_TOOLS
    TOOL_REGISTRY --> QUAL_TOOLS

    COMP_FACTORY --> LLM_CLIENT
    QUAL_FACTORY --> LLM_CLIENT
    DEC_FACTORY --> LLM_CLIENT
    VERIFIER --> LLM_CLIENT

    ROUTER --> MONGO_DB
    ROUTER --> REDIS_CLIENT
    ROUTER --> MILVUS_CLIENT
    ROUTER --> OCR_CLIENT

    style GRAPH fill:#c8e6c9
    style SKILL_LOADER fill:#ffe0b2
    style CHECKPOINT fill:#b39ddb
```

### 5.3 Biểu đồ luồng dữ liệu tổng quát (Data Flow)

```mermaid
graph LR
    subgraph "Input"
        USER[User Uploads<br/>Claim Documents]
        FILE[Document File<br/>PDF/Image]
    end

    subgraph "Preprocessing"
        HASH[Calculate SHA-256]
        CACHE_CHECK[(Check Cache<br/>MongoDB)]
    end

    subgraph "OCR Processing"
        OCR_REQ[OCR Service Request]
        GEMINI_VISION[Gemini Vision API]
        EXTRACTED[Extracted Text<br/>Structured Data]
    end

    subgraph "Workflow State"
        STATE[GraphState<br/>TypedDict]
        HISTORY[History<br/>Accumulated Actions]
    end

    subgraph "Agent Processing"
        COMP[Completeness Agent]
        QUAL[Quality Agent]
        DEC[Decision Agent]
        VERIFIER[Verifier Agent]
    end

    subgraph "Tool Execution"
        ICD_CHECK[ICD Lookup]
        MED_CHECK[Medication Search]
        EXCLUSION[Exclusion Check]
        BENEFIT[Benefit Classification]
    end

    subgraph "Review & Decision"
        AGENT_REVIEW[Agent Review]
        HUMAN[Human Review]
        FINAL[Final Decision]
    end

    subgraph "Output"
        AUDIT[(Audit Logs<br/>MongoDB)]
        RESULT[Final Result<br/>JSON Response]
        LANGFUSE[Langfuse Traces]
    end

    USER --> FILE
    FILE --> HASH
    HASH --> CACHE_CHECK

    CACHE_CHECK -->|Cache Hit| STATE
    CACHE_CHECK -->|Cache Miss| OCR_REQ

    OCR_REQ --> GEMINI_VISION
    GEMINI_VISION --> EXTRACTED
    EXTRACTED --> STATE

    STATE --> COMP
    STATE --> QUAL
    STATE --> DEC
    STATE --> VERIFIER

    COMP --> ICD_CHECK
    COMP --> BENEFIT
    QUAL --> MED_CHECK
    QUAL --> EXCLUSION
    QUAL --> ICD_CHECK

    ICD_CHECK --> STATE
    MED_CHECK --> STATE
    EXCLUSION --> STATE
    BENEFIT --> STATE

    COMP --> AGENT_REVIEW
    QUAL --> AGENT_REVIEW
    AGENT_REVIEW --> VERIFIER
    VERIFIER -->|Auto-approved| QUAL
    VERIFIER -->|Escalate| HUMAN

    DEC --> HUMAN
    HUMAN --> FINAL
    FINAL --> RESULT

    STATE --> HISTORY
    HISTORY --> AUDIT
    STATE --> LANGFUSE

    style STATE fill:#e8f5e9
    style AUDIT fill:#fff9c4
    style LANGFUSE fill:#b3e5fc
```

### 5.4 Nguyên tắc tích hợp và giao tiếp giữa các thành phần

```mermaid
sequenceDiagram
    participant User
    participant UI as WebUI
    participant API as Agent API
    participant Graph as LangGraph
    participant Agent as Agent Nodes
    participant Tool as Tool System
    participant DB as MongoDB
    participant Redis as Redis
    participant LLM as Gemini API

    User->>UI: Upload Claim Document
    UI->>API: POST /api/v1/workflows/run
    API->>DB: Check file hash cache
    alt Cache Hit
        DB-->>API: Return cached OCR result
    else Cache Miss
        API->>API: Call OCR Service
    end
    API->>Graph: Create StateGraph instance
    Graph->>DB: Initialize checkpoint
    Graph->>Redis: Map claim_id to thread_id

    loop Workflow Execution
        Graph->>Agent: Execute node
        Agent->>Tool: Load agent skills
        Tool->>Tool: Load tools from skills/
        Agent->>LLM: Invoke agent with tools
        LLM->>Tool: Execute tool calls
        Tool-->>LLM: Return results
        LLM-->>Agent: Return agent output
        Agent->>DB: Save audit log (async)
        Agent->>Graph: Update state

        alt Requires Human Review
            Graph-->>API: Interrupt before human_review
            API-->>UI: Send pause event
            UI->>User: Display review panel
            User->>UI: Submit decision
            UI->>API: POST /api/v1/workflows/resume
            API->>Graph: Update state with human decision
            Graph->>Graph: Resume workflow
        end

        Graph->>Graph: Conditional routing
    end

    Graph-->>API: Final result
    API->>DB: Save final state
    API-->>UI: Return complete result
    UI-->>User: Display final decision
```

---

## 6. Thiết kế kiến trúc đa tác nhân dựa trên LangGraph

### 6.2 Thiết kế các tác nhân chuyên biệt (Agent Roles)

#### Bảng định nghĩa đầu vào và đầu ra của tác nhân

| Tác nhân | Đầu vào | Đầu ra | Công cụ sử dụng |
|----------|---------|--------|----------------|
| **CompletenessAgent** | claim_id, policy_number, extracted_documents, history | AssessmentOutput (valid, decision, issues, suggested_updates, evidence) | check-required-docs, validate-consistency, classify-benefit |
| **QualityAgent** | claim_id, policy_number, extracted_documents, history | AssessmentOutput (valid, decision, issues, medical_findings, suggested_updates) | check-icd, validate-medication, check-exclusion, search-medicine, web-search |
| **DecisionAgent** | claim_id, policy_number, agent_1_result, agent_2_result, human_review_result | FinalDecisionOutput (decision, approved_amount, rejection_reason, issues_summary) | aggregate-issues |
| **VerifierAgent** | primary_assessment, extracted_evidence, extracted_documents, current_step | VerifierOutput (verdict, reason, contradictions) | Cross-verification logic |

### 6.3 Thiết kế đồ thị xử lý (Graph Topology)

```mermaid
graph TB
    START((Start)) --> COMPLETENESS[Completeness Check]

    COMPLETENESS -->|accept| QUALITY[Quality Check]
    COMPLETENESS -->|reject| DECISION[Final Decision]
    COMPLETENESS -->|accept_with_edit| AGENT_REVIEW1[Agent Review]

    QUALITY -->|accept| DECISION
    QUALITY -->|reject| DECISION
    QUALITY -->|accept_with_edit| AGENT_REVIEW2[Agent Review]

    AGENT_REVIEW1 -->|Auto-approved| QUALITY
    AGENT_REVIEW1 -->|Escalate| HUMAN1[Human Review]
    AGENT_REVIEW2 -->|Auto-approved| DECISION
    AGENT_REVIEW2 -->|Escalate| HUMAN2[Human Review]

    DECISION -->|edit| QUALITY
    DECISION -->|otherwise| HUMAN3[Human Review]

    HUMAN1 -->|approve| QUALITY
    HUMAN1 -->|reject| DECISION
    HUMAN1 -->|edit| COMPLETENESS

    HUMAN2 -->|approve| DECISION
    HUMAN2 -->|reject| DECISION
    HUMAN2 -->|edit| QUALITY

    HUMAN3 -->|approve| END((End))
    HUMAN3 -->|reject| END
    HUMAN3 -->|edit| QUALITY

    style COMPLETENESS fill:#81c784
    style QUALITY fill:#64b5f6
    style DECISION fill:#ba68c8
    style AGENT_REVIEW1 fill:#ffd54f
    style AGENT_REVIEW2 fill:#ffd54f
    style HUMAN1 fill:#ff8a65
    style HUMAN2 fill:#ff8a65
    style HUMAN3 fill:#ff8a65
```

### 6.3.1 Lược đồ trạng thái dùng chung (State Schema)

```mermaid
erDiagram
    GRAPHSTATE {
        string run_id "Run identifier"
        string claim_id "Claim ID"
        string policy_number "Policy number"
        string input_file "Input file path"
        dict extracted_documents "OCR results"
        dict agent_1_result "Completeness result"
        dict agent_2_result "Quality result"
        dict human_review_result "Human review decision"
        dict edited_agent_1_result "Human-edited completeness"
        dict edited_agent_2_result "Human-edited quality"
        dict final_result "Final decision"
        list history "Accumulated actions"
        string current_step "Current workflow step"
        bool should_continue "Continue flag"
        string error "Error message if any"
        bool pending_human_review "Human review pending"
    }

    ASSESSMENT_OUTPUT {
        bool valid "Overall validity"
        string decision "accept/reject/accept_with_edit"
        list issues "Found issues"
        string message "Summary message"
        float confidence_score "0.0 - 1.0"
        bool is_auto_reviewed "Auto-reviewed flag"
        list suggested_updates "Suggested edits"
        dict evidence "Extracted evidence"
        object medical_findings "Quality results"
    }

    FINAL_DECISION_OUTPUT {
        string decision "approve/reject"
        int approved_amount "Approved amount"
        string rejection_reason "Rejection reason"
        list issues_summary "Issue summary"
        string message "Decision explanation"
    }

    VERIFIER_OUTPUT {
        string verdict "pass/fail"
        string reason "Explanation"
        list contradictions "Found contradictions"
    }

    GRAPHSTATE ||--|| ASSESSMENT_OUTPUT : "agent_1_result"
    GRAPHSTATE ||--|| ASSESSMENT_OUTPUT : "agent_2_result"
    GRAPHSTATE ||--|| FINAL_DECISION_OUTPUT : "final_result"
    GRAPHSTATE ||--|| VERIFIER_OUTPUT : "verifier_result"
```

### 6.3.2 Cơ chế điều hướng và định tuyến có điều kiện (Conditional Routing)

```mermaid
graph TB
    subgraph "Completeness Check Routing"
        COMP_RESULT[completeness_check<br/>result]
        COMP_DECISION{decision field?}

        COMP_RESULT --> COMP_DECISION
        COMP_DECISION -->|accept| NEXT_QUALITY[→ quality_check]
        COMP_DECISION -->|reject| NEXT_FINAL[→ final_decision]
        COMP_DECISION -->|accept_with_edit| NEXT_AGENT_REVIEW[→ agent_review]

        COMP_DECISION -->|critical/high<br/>issues| NEXT_FINAL
        COMP_DECISION -->|medium/low<br/>issues| NEXT_AGENT_REVIEW
    end

    subgraph "Quality Check Routing"
        QUAL_RESULT[quality_check<br/>result]
        QUAL_DECISION{decision field?}

        QUAL_RESULT --> QUAL_DECISION
        QUAL_DECISION -->|accept| NEXT_FINAL2[→ final_decision]
        QUAL_DECISION -->|reject| NEXT_FINAL2
        QUAL_DECISION -->|accept_with_edit| NEXT_AGENT_REVIEW2[→ agent_review]
    end

    subgraph "Agent Review Routing"
        AGENT_REV_RESULT[agent_review<br/>result]
        AUTO_CHECK{is_auto_reviewed?}

        AGENT_REV_RESULT --> AUTO_CHECK
        AUTO_CHECK -->|True| STAGE_CHECK{current_step?}
        AUTO_CHECK -->|False| NEXT_HUMAN[→ human_review]

        STAGE_CHECK -->|completeness| NEXT_QUALITY2[→ quality_check]
        STAGE_CHECK -->|quality| NEXT_FINAL3[→ final_decision]
    end

    subgraph "Final Decision Routing"
        FINAL_RESULT[final_decision<br/>result]
        FINAL_CHECK{decision field?}

        FINAL_RESULT --> FINAL_CHECK
        FINAL_CHECK -->|edit| NEXT_QUALITY3[→ quality_check]
        FINAL_CHECK -->|otherwise| NEXT_HUMAN2[→ human_review]
    end

    subgraph "Human Review Routing"
        HUMAN_RESULT[human_review_result]
        STAGE_DETERMINE{stage?}

        HUMAN_RESULT --> STAGE_DETERMINE
        STAGE_DETERMINE -->|completeness| HUMAN_COMP_DECISION{decision?}
        STAGE_DETERMINE -->|quality| HUMAN_QUAL_DECISION{decision?}
        STAGE_DETERMINE -->|final/None| HUMAN_FINAL_DECISION{decision?}

        HUMAN_COMP_DECISION -->|approve| NEXT_QUALITY4[→ quality_check]
        HUMAN_COMP_DECISION -->|reject| NEXT_FINAL4[→ final_decision]
        HUMAN_COMP_DECISION -->|edit| NEXT_COMP[→ completeness_check]

        HUMAN_QUAL_DECISION -->|approve| NEXT_FINAL5[→ final_decision]
        HUMAN_QUAL_DECISION -->|reject| NEXT_FINAL5
        HUMAN_QUAL_DECISION -->|edit| NEXT_QUALITY5[→ quality_check]

        HUMAN_FINAL_DECISION -->|approve| END[→ END]
        HUMAN_FINAL_DECISION -->|reject| END
        HUMAN_FINAL_DECISION -->|edit| NEXT_QUALITY6[→ quality_check]
    end

    style COMP_RESULT fill:#81c784
    style QUAL_RESULT fill:#64b5f6
    style FINAL_RESULT fill:#ba68c8
    style AGENT_REV_RESULT fill:#ffd54f
    style HUMAN_RESULT fill:#ff8a65
    style END fill:#ef5350
```

### 6.4 Cơ chế phối hợp và tương tác giữa các tác nhân

```mermaid
sequenceDiagram
    participant Graph as StateGraph
    participant Comp as CompletenessAgent
    participant Qual as QualityAgent
    participant Dec as DecisionAgent
    participant Reviewer as AgentReviewNode
    participant Verifier as VerifierAgent
    participant Human as HumanReviewNode

    Graph->>Comp: Execute with extracted_documents
    Comp->>Comp: Load skills (check-docs, validate-consistency)
    Comp->>Comp: Use tools to verify completeness
    Comp->>Graph: Return AssessmentOutput

    alt decision == accept_with_edit
        Graph->>Reviewer: Agent review triggered
        Reviewer->>Reviewer: Check hard constraints
        Reviewer->>Reviewer: Check confidence threshold
        alt confidence >= threshold AND safe
            Reviewer->>Verifier: Cross-verify assessment
            Verifier->>Verifier: Check for contradictions
            Verifier-->>Reviewer: VerifierOutput
            alt verdict == pass
                Reviewer->>Graph: Set is_auto_reviewed=True
                Graph->>Qual: Continue to quality check
            else
                Reviewer->>Graph: Set is_auto_reviewed=False
                Graph->>Human: Interrupt for human review
            end
        else
            Reviewer->>Graph: Escalate to human review
        end
    else decision == accept
        Graph->>Qual: Direct to quality check
    else decision == reject
        Graph->>Dec: Direct to final decision
    end

    Qual->>Qual: Load skills (check-icd, validate-medication, check-exclusion)
    Qual->>Qual: Use tools including web search
    Qual->>Graph: Return AssessmentOutput with medical_findings

    alt quality check passes
        Graph->>Dec: Make final decision
        Dec->>Dec: Aggregate all issues from both agents
        Dec->>Graph: Return FinalDecisionOutput
        Graph->>Human: Force human sign-off
    else quality has issues
        Graph->>Reviewer: Agent review for quality
    end
```

### 6.5 Cơ chế quản lý trạng thái bền vững (Persistence & Checkpointing)

```mermaid
graph TB
    subgraph "LangGraph Checkpoint System"
        STATE[GraphState<br/>TypedDict]
        REDUCER[operator.add<br/>for history]
    end

    subgraph "Checkpoint Storage"
        MONGO_CP[(MongoDB<br/>Checkpoint Collection)]
        THREAD_ID[thread_id<br/>Identifier]
    end

    subgraph "Session Management"
        CLAIM_ID[claim_id]
        REDIS_MAP[(Redis<br/>claim_id → thread_id)]
    end

    subgraph "Interrupt Mechanism"
        INTERRUPT[interrupt_before<br/>human_review]
        PAUSED[Paused State<br/>pending_human_review=True]
    end

    subgraph "Resume Flow"
        RESUME[POST /resume/{run_id}]
        UPDATE[Update state<br/>human_review_result]
        CONTINUE[Resume execution]
    end

    STATE --> REDUCER
    REDUCER --> MONGO_CP
    MONGO_CP --> THREAD_ID

    CLAIM_ID --> REDIS_MAP
    REDIS_MAP --> THREAD_ID

    STATE --> INTERRUPT
    INTERRUPT --> PAUSED
    PAUSED --> MONGO_CP

    PAUSED --> RESUME
    RESUME --> UPDATE
    UPDATE --> MONGO_CP
    MONGO_CP --> CONTINUE

    style STATE fill:#e8f5e9
    style MONGO_CP fill:#f3e5f5
    style REDIS_MAP fill:#fce4ec
    style PAUSED fill:#fff9c4
```

---

## 7. Thiết kế dữ liệu và trạng thái xử lý

### 7.1 Mô hình dữ liệu yêu cầu và kết quả thẩm định

```mermaid
classDiagram
    class ClaimRequest {
        +str claim_id
        +str policy_number
        +str input_file
        +str file_hash
    }

    class HumanReviewRequest {
        +str decision
        +str notes
        +dict edited_result
    }

    class UploadResponse {
        +str filename
        +str file_path
        +int size_bytes
        +str file_hash
    }

    class AssessmentOutput {
        +bool valid
        +str decision
        +List~Issue~ issues
        +str message
        +float confidence_score
        +bool is_auto_reviewed
        +List~SuggestedUpdate~ suggested_updates
        +dict evidence
        +MedicalQualityFindings medical_findings
    }

    class FinalDecisionOutput {
        +str decision
        +int approved_amount
        +str rejection_reason
        +List~IssueSummary~ issues_summary
        +str message
    }

    class VerifierOutput {
        +str verdict
        +str reason
        +List~str~ contradictions
    }

    class Issue {
        +str severity
        +str code
        +str description
        +str reason
    }

    class SuggestedUpdate {
        +str field
        +str current_value
        +str suggested_value
        +str reference_url
    }

    class QualityWarning {
        +str type
        +str diagnosis_name
        +str suggested_icd
        +str message
        +str reference_url
    }

    class QualitySuccess {
        +str type
        +str diagnosis_name
        +str icd
        +str message
        +str reference_url
    }

    class MedicalQualityData {
        +dict summary
        +List~QualityWarning~ warnings
        +List~QualitySuccess~ success
    }

    class MedicalQualityFindings {
        +str status_message
        +MedicalQualityData data
    }

    class IssueSummary {
        +str category
        +int count
        +str severity
    }

    ClaimRequest --> AssessmentOutput
    HumanReviewRequest --> FinalDecisionOutput
    AssessmentOutput --> Issue
    AssessmentOutput --> SuggestedUpdate
    AssessmentOutput --> MedicalQualityFindings
    MedicalQualityFindings --> MedicalQualityData
    MedicalQualityData --> QualityWarning
    MedicalQualityData --> QualitySuccess
    FinalDecisionOutput --> IssueSummary
```

### 7.3 Thiết kế lưu trữ nhật ký kiểm toán (Audit Trail)

```mermaid
erDiagram
    AUDIT_LOGS {
        ObjectId _id
        string run_id
        string claim_id
        string step_name
        string agent_name
        dict result_json
        datetime timestamp
        string error
    }

    CHECKPOINTS {
        ObjectId _id
        string thread_id
        string checkpoint_id
        string checkpoint_ns
        string channel_id
        GraphState state
        dict metadata
        datetime timestamp
    }

    DOCUMENT_CACHE {
        ObjectId _id
        string file_hash
        string claim_id
        dict ocr_result
        datetime created_at
        datetime last_accessed
    }

    THREAD_MAPPING {
        string claim_id
        string thread_id
        string run_id
        datetime created_at
    }

    AUDIT_LOGS ||--|| CHECKPOINTS : "associated with"
    AUDIT_LOGS ||--|| DOCUMENT_CACHE : "references"
    AUDIT_LOGS ||--|| THREAD_MAPPING : "uses"
    CHECKPOINTS ||--|| THREAD_MAPPING : "stores"
```

---

## 8. Thiết kế quy trình xử lý nghiệp vụ chi tiết

### 8.1 Quy trình tiếp nhận và tiền xử lý dữ liệu

```mermaid
flowchart TD
    START([User submits claim]) --> UPLOAD
    UPLOAD[Upload document<br/>to OCR Service] --> CALC_HASH
    CALC_HASH[Calculate SHA-256<br/>file hash] --> CHECK_CACHE

    CHECK_CACHE{Cache exists?}
    CHECK_CACHE -->|Yes| USE_CACHE[Use cached<br/>OCR result]
    CHECK_CACHE -->|No| CALL_OCR[Call OCR Service]

    CALL_OCR --> GEMINI_VISION
    GEMINI_VISION[Gemini Vision API<br/>extract text] --> PARSE_RESULT
    PARSE_RESULT[Parse structured<br/>data] --> SAVE_CACHE
    SAVE_CACHE[Save to MongoDB<br/>document_cache] --> USE_CACHE

    USE_CACHE --> INIT_STATE
    INIT_STATE[Initialize GraphState] --> CREATE_THREAD
    CREATE_THREAD[Generate thread_id<br/>for LangGraph] --> MAP_THREAD
    MAP_THREAD[Map claim_id<br/>to thread_id in Redis] --> START_WORKFLOW

    START_WORKFLOW[Start LangGraph<br/>workflow] --> COMPLETENESS

    style UPLOAD fill:#e1f5ff
    style CALL_OCR fill:#fff4e1
    style USE_CACHE fill:#e8f5e9
    style INIT_STATE fill:#c8e6c9
```

### 8.2 Quy trình phân tích và đối soát nghiệp vụ tự động

```mermaid
flowchart TD
    subgraph "Completeness Check"
        COMP_START[Start Completeness Agent] --> LOAD_COMP_SKILLS
        LOAD_COMP_SKILLS[Load skills:<br/>check-required-docs,<br/>validate-consistency] --> EXEC_COMP_TOOLS
        EXEC_COMP_TOOLS[Execute tools] --> COMP_ANALYZE
        COMP_ANALYZE[Analyze documents<br/>for completeness] --> COMP_DECIDE
        COMP_DECIDE{Completeness<br/>status?}

        COMP_DECIDE -->|All required<br/>docs present| COMP_ACCEPT[Decision: accept]
        COMP_DECIDE -->|Critical issues| COMP_REJECT[Decision: reject]
        COMP_DECIDE -->|Minor issues<br/>with fixes| COMP_EDIT[Decision: accept_with_edit]
    end

    subgraph "Quality Check"
        QUAL_START[Start Quality Agent] --> LOAD_QUAL_SKILLS
        LOAD_QUAL_SKILLS[Load skills:<br/>check-icd,<br/>validate-medication,<br/>check-exclusion,<br/>web-search] --> EXEC_QUAL_TOOLS
        EXEC_QUAL_TOOLS[Execute tools<br/>including web search] --> QUAL_ANALYZE
        QUAL_ANALYZE[Validate medical<br/>quality & compliance] --> QUAL_DECIDE
        QUAL_DECIDE{Quality<br/>status?}

        QUAL_DECIDE -->|All valid| QUAL_ACCEPT[Decision: accept]
        QUAL_DECIDE -->|Serious violations| QUAL_REJECT[Decision: reject]
        QUAL_DECIDE -->|Minor issues<br/>with corrections| QUAL_EDIT[Decision: accept_with_edit]
    end

    subgraph "Agent Review (for accept_with_edit)"
        REVIEW_START[Agent Review Node] --> CHECK_CONSTRAINTS
        CHECK_CONSTRAINTS[Check hard constraints:<br/>amount threshold,<br/>issue severity] --> CONSTRAINTS_OK?

        CONSTRAINTS_OK? -->|Pass| CHECK_CONFIDENCE
        CONSTRAINTS_OK? -->|Fail| ESCALATE[Escalate to human]

        CHECK_CONFIDENCE[Check confidence<br/>score >= threshold] --> CONFIDENCE_OK?
        CONFIDENCE_OK? -->|Yes| CALL_VERIFIER
        CONFIDENCE_OK? -->|No| ESCALATE

        CALL_VERIFIER[Call Verifier Agent] --> VERIFY_RESULT
        VERIFY_RESULT{Verdict?}
        VERIFY_RESULT -->|pass & no<br/>contradictions| AUTO_APPROVE[Set is_auto_reviewed=True]
        VERIFY_RESULT -->|fail or<br/>contradictions| ESCALATE
    end

    COMP_ACCEPT --> QUAL_START
    COMP_REJECT --> FINAL_DEC
    COMP_EDIT --> REVIEW_START

    QUAL_ACCEPT --> FINAL_DEC
    QUAL_REJECT --> FINAL_DEC
    QUAL_EDIT --> REVIEW_START

    AUTO_APPROVE --> QUAL_START
    AUTO_APPROVE --> FINAL_DEC

    subgraph "Final Decision"
        FINAL_DEC[Decision Agent] --> AGGREGATE
        AGGREGATE[Aggregate all<br/>issues & findings] --> MAKE_DECISION
        MAKE_DECISION{Final<br/>decision?}

        MAKE_DECISION -->|approve| FORCE_HUMAN[Force human<br/>sign-off]
        MAKE_DECISION -->|reject| FORCE_HUMAN
        MAKE_DECISION -->|edit| LOOP_BACK[Loop to quality<br/>for updates]
    end

    LOOP_BACK --> QUAL_START

    style COMP_START fill:#81c784
    style QUAL_START fill:#64b5f6
    style REVIEW_START fill:#ffd54f
    style FINAL_DEC fill:#ba68c8
    style AUTO_APPROVE fill:#a5d6a7
    style ESCALATE fill:#ef9a9a
```

### 8.3 Cơ chế cộng tác Người-AI (Human-in-the-Loop)

```mermaid
sequenceDiagram
    participant Graph as LangGraph
    participant API as API Service
    participant UI as Web Interface
    participant Human as Human Reviewer
    participant DB as MongoDB

    Note over Graph, DB: Automated Processing
    Graph->>Graph: Execute completeness_check
    Graph->>Graph: Execute quality_check

    alt Issue found requiring review
        Graph->>Graph: Route to agent_review
        Graph->>Graph: Agent review fails confidence/verifier
        Graph->>API: State = pending_human_review
        Graph->>DB: Save checkpoint
        Graph->>API: Interrupt before human_review
        API->>UI: SSE event: pending_human_review
        UI->>Human: Display review panel
    end

    Note over UI, Human: Human Review Phase
    Human->>UI: Review agent results
    Human->>UI: Make decision
    Human->>UI: Optionally edit fields
    UI->>API: POST /api/v1/workflows/resume
    API->>API: Update human_review_result in state
    API->>DB: Update checkpoint

    Note over Graph, DB: Resume Workflow
    API->>Graph: POST /api/v1/workflows/continue
    Graph->>Graph: Execute human_review (no-op)
    Graph->>Graph: Route based on human decision

    alt Human approved
        Graph->>Graph: Continue to next stage
        Graph->>Graph: Execute final_decision
    else Human rejected
        Graph->>Graph: Route to final_decision for rejection
    else Human edited
        Graph->>Graph: Route back to quality_check with edits
    end

    Graph->>DB: Save final checkpoint
    Graph->>API: Return final result
    API->>UI: Send final decision
    UI->>Human: Display approved/rejected status
```

### 8.4 Quy trình tổng hợp và phản hồi kết quả

```mermaid
flowchart LR
    subgraph "Result Aggregation"
        AGG_START[Final Decision Agent] --> COLLECT
        COLLECT[Collect results:<br/>agent_1_result,<br/>agent_2_result,<br/>human_review_result] --> ANALYZE
        ANALYZE[Analyze aggregated data] --> DETERMINE
        DETERMINE[Determine final<br/>decision] --> CALC_AMOUNT
        CALC_AMOUNT[Calculate approved<br/>amount] --> GENERATE
    end

    subgraph "Response Generation"
        GENERATE[Generate FinalDecisionOutput] --> CREATE_SUMMARY
        CREATE_SUMMARY[Create issues summary<br/>by category] --> EXPLAIN
        EXPLAIN[Write detailed<br/>explanation] --> FINAL_OUTPUT
    end

    subgraph "Response Delivery"
        FINAL_OUTPUT[Final JSON Response] --> AUDIT_LOG
        AUDIT_LOG[Save to audit_logs<br/>collection] --> SSE_STREAM
        SSE_STREAM[Stream via SSE<br/>to client] --> UI_UPDATE
        UI_UPDATE[Update Web UI<br/>dashboard] --> NOTIFICATION
        NOTIFICATION[Send notification<br/>to user]
    end

    subgraph "Audit & Observability"
        AUDIT_LOG --> LANGFUSE
        LANGFUSE[Send trace to<br/>Langfuse] --> ANALYTICS
        ANALYTICS[Store metrics &<br/>performance data]
    end

    style AGG_START fill:#ba68c8
    style GENERATE fill:#9575cd
    style FINAL_OUTPUT fill:#7e57c2
    style AUDIT_LOG fill:#fff9c4
    style LANGFUSE fill:#b3e5fc
```

---

## 9. Thiết kế cơ chế giám sát và giải trình

### 9.1 Kiến trúc giám sát hiệu năng với Langfuse

```mermaid
graph TB
    subgraph "Application Layer"
        AGENT[Agent Service]
        WORKFLOW[LangGraph Workflow]
    end

    subgraph "LangChain Integration"
        LANGCHAIN[LangChain Tracing<br/>@observe decorator]
        LLM_CALL[LLM Calls]
        TOOL_CALL[Tool Invocations]
    end

    subgraph "Langfuse SDK"
        SDK_INIT[Langfuse.init]
        OBSERVER[@observe<br/>decorator]
        TRACE[Trace Object]
        SPAN[Span Object]
    end

    subgraph "Langfuse Platform"
        INGESTION[Ingestion API]
        STORAGE[(Trace Storage)]
        DASHBOARD[Langfuse Dashboard]
        ANALYTICS[Analytics Engine]
    end

    subgraph "Monitoring Data"
        TRACES[Trace Data<br/>workflow executions]
        SPANS[Span Data<br/>individual operations]
        METRICS[Metrics<br/>latency, tokens, costs]
        FEEDBACK[Feedback<br/>user ratings]
    end

    AGENT --> LANGCHAIN
    WORKFLOW --> LANGCHAIN

    LANGCHAIN --> LLM_CALL
    LANGCHAIN --> TOOL_CALL

    AGENT --> SDK_INIT
    SDK_INIT --> OBSERVER
    OBSERVER --> TRACE
    OBSERVER --> SPAN

    TRACE --> INGESTION
    SPAN --> INGESTION
    LLM_CALL --> SPAN
    TOOL_CALL --> SPAN

    INGESTION --> STORAGE
    STORAGE --> DASHBOARD
    STORAGE --> ANALYTICS

    STORAGE --> TRACES
    STORAGE --> SPANS
    ANALYTICS --> METRICS
    DASHBOARD --> FEEDBACK

    style AGENT fill:#e8f5e9
    style LANGCHAIN fill:#fff4e1
    style SDK_INIT fill:#e1f5ff
    style INGESTION fill:#c8e6c9
    style DASHBOARD fill:#b3e5fc
    style STORAGE fill:#f3e5f5
```

### 9.2 Cơ chế truy vết chuỗi tư duy (Chain-of-Thought)

```mermaid
sequenceDiagram
    participant User
    participant Agent as LangGraph Agent
    participant LLM as Gemini API
    participant Tool as Tool System
    participant Langfuse as Langfuse Trace
    participant Audit as MongoDB Audit

    User->>Agent: Process claim request
    Agent->>Langfuse: Create Trace<br/>name="completeness_check_<claim_id>"
    Langfuse-->>Agent: trace_id

    Agent->>LLM: Invoke with system prompt<br/>+ extracted data
    Agent->>Langfuse: Create Span<br/>type="llm"
    LLM->>Tool: Tool call: check_required_docs
    Tool->>Langfuse: Create Span<br/>type="tool"
    Tool->>Tool: Execute logic
    Tool-->>LLM: Tool result
    Tool->>Langfuse: End span with output

    LLM->>Tool: Tool call: validate_consistency
    Tool->>Langfuse: Create Span<br/>type="tool"
    Tool->>Tool: Execute logic
    Tool-->>LLM: Tool result
    Tool->>Langfuse: End span with output

    LLM->>LLM: Chain-of-thought<br/>reasoning
    LLM->>Langfuse: Log LLM response<br/>with usage/tokens
    LLM-->>Agent: Structured JSON output
    Agent->>Langfuse: End LLM span

    Agent->>Agent: Parse & validate output
    Agent->>Langfuse: Update Trace metadata
    Agent->>Audit: Save audit log with<br/>trace_id, result, timestamp

    Agent-->>User: Return assessment result

    Note over Langfuse, Audit: All steps captured with:<br/>- Execution order<br/>- Input/Output<br/>- Token usage<br/>- Latency<br/>- Error states
```

### 9.3 Thiết kế báo cáo giải trình kết quả thẩm định

```mermaid
graph TB
    subgraph "Execution Evidence"
        STATE[GraphState<br/>Complete state snapshot]
        HISTORY[History Array<br/>Step-by-step actions]
        AUDIT[Audit Logs<br/>Per-step records]
        TRACE[Langfuse Trace<br/>LLM interactions]
    end

    subgraph "Decision Evidence"
        AGENT_1[Completeness<br/>Assessment]
        AGENT_2[Quality<br/>Assessment]
        VERIFIER[Verifier<br/>Cross-check]
        FINAL[Final<br/>Decision]
    end

    subgraph "Evidence Items"
        ISSUES[Issue List<br/>With severity & codes]
        SUGGESTIONS[Suggested Updates<br/>With reference URLs]
        EVIDENCE_DATA[Extracted Evidence<br/>From documents]
        MEDICAL_FINDINGS[Medical Quality<br/>Warnings & Success]
        CONTRADICTIONS[Detected<br/>Contradictions]
    end

    subgraph "Explanation Generation"
        AGGREGATE[Aggregate all<br/>evidence items]
        SUMMARIZE[Create issue<br/>summaries]
        EXPLAIN[Generate Vietnamese<br/>explanations]
        REFERENCE[Add reference<br/>links]
    end

    subgraph "Final Report"
        REPORT[Comprehensive<br/>Audit Report]
        JSON_OUTPUT[Structured<br/>JSON Response]
        UI_DISPLAY[Human-readable<br/>Dashboard View]
    end

    STATE --> HISTORY
    STATE --> AUDIT
    AUDIT --> TRACE
    HISTORY --> AGENT_1
    HISTORY --> AGENT_2
    HISTORY --> VERIFIER
    HISTORY --> FINAL

    AGENT_1 --> ISSUES
    AGENT_1 --> SUGGESTIONS
    AGENT_1 --> EVIDENCE_DATA
    AGENT_2 --> MEDICAL_FINDINGS
    AGENT_2 --> ISSUES
    AGENT_2 --> SUGGESTIONS
    VERIFIER --> CONTRADICTIONS

    ISSUES --> AGGREGATE
    SUGGESTIONS --> AGGREGATE
    EVIDENCE_DATA --> AGGREGATE
    MEDICAL_FINDINGS --> AGGREGATE
    CONTRADICTIONS --> AGGREGATE

    AGGREGATE --> SUMMARIZE
    SUMMARIZE --> EXPLAIN
    EXPLAIN --> REFERENCE

    REFERENCE --> REPORT
    REPORT --> JSON_OUTPUT
    REPORT --> UI_DISPLAY

    style STATE fill:#e8f5e9
    style AUDIT fill:#fff9c4
    style TRACE fill:#b3e5fc
    style AGGREGATE fill:#ffcc80
    style REPORT fill:#a5d6a7
```

---

## Phụ lục: Chú thích kỹ thuật

### Ký hiệu đồ thị

| Ký hiệu | Ý nghĩa |
|---------|---------|
| `[]` | Thành phần/Component |
| `()` | Sự kiện/Event |
| `(())` | Bắt đầu/Kết thúc |
| `{}` | Điều kiện rẽ nhánh |
| `||--||` | Mối quan hệ một-một |
| `||--o{` | Mối quan hệ một-nhiều |

### Màu sắc biểu đồ

| Màu sắc | Thành phần |
|---------|------------|
| 🟢 Xanh lá | Completeness Agent, State, Success |
| 🔵 Xanh dương | Quality Agent, Database, Tools |
| 🟡 Vàng | Agent Review, Human-in-the-loop |
| 🟣 Tím | Decision Agent, Final Output |
| 🔴 Đỏ | Rejection, Errors, Escalation |
| 🟠 Cam | Human Review, External Services |
| 🟤 Nâu | Infrastructure, Storage |

### Ràng buộc hệ thống

| Ràng buộc | Giá trị mặc định | Mô tả |
|-----------|-----------------|--------|
| `AGENT_REVIEW_AMOUNT_THRESHOLD` | 5,000,000 VNĐ | Ngưỡng số tiền cho auto-approve |
| `AGENT_REVIEW_CONFIDENCE_THRESHOLD` | 0.9 | Độ tin cậy tối thiểu cho auto-approve |
| Mức độ vấn đề nghiêm trọng | critical, high, medium, low | Phân loại độ nghiêm trọng |
| Quyết định tác nhân | accept, reject, accept_with_edit | Các loại quyết định có thể |
| Quyết định cuối cùng | approve, reject, edit | Quyết định cuối cùng của hệ thống |
