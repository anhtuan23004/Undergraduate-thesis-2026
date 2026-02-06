// Initialize claims database
db = db.getSiblingDB('claims');

// Create collections
db.createCollection('agent_sessions');
db.createCollection('documents');
db.createCollection('extractions');
db.createCollection('audit_logs');
db.createCollection('workflows');
db.createCollection('agent_checkpoints');

// Create indexes for agent_sessions
db.agent_sessions.createIndex({ "session_id": 1 }, { unique: true });
db.agent_sessions.createIndex({ "created_at": 1 });
db.agent_sessions.createIndex({ "agent_type": 1 });
db.agent_sessions.createIndex({ "claim_id": 1 });

// Create indexes for documents
db.documents.createIndex({ "claim_id": 1 });
db.documents.createIndex({ "document_type": 1 });
db.documents.createIndex({ "status": 1 });
db.documents.createIndex({ "created_at": 1 });

// Create indexes for extractions
db.extractions.createIndex({ "claim_id": 1 });
db.extractions.createIndex({ "extraction_status": 1 });
db.extractions.createIndex({ "created_at": 1 });

// Create indexes for audit_logs
db.audit_logs.createIndex({ "timestamp": -1 });
db.audit_logs.createIndex({ "user_id": 1 });
db.audit_logs.createIndex({ "action_type": 1 });
db.audit_logs.createIndex({ "claim_id": 1 });

// Create indexes for agent_checkpoints (LangGraph state)
db.agent_checkpoints.createIndex({ "thread_id": 1 }, { unique: true });
db.agent_checkpoints.createIndex({ "timestamp": -1 });
db.agent_checkpoints.createIndex({ "iteration": 1 });

// Create user for application
db.createUser({
    user: "claims_app",
    pwd: "claims_password",
    roles: [
        { role: "readWrite", db: "claims" }
    ]
});

print('Claims database initialized successfully');
