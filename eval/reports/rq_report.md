# Evaluation RQ Report

- Label source: `eval/results/reviewed_labels.json`
- Labelled claim count: 80
- Result count: 130

## RQ1

Final decision correctness against reference labels.

```json
{
  "question": "Final decision correctness against reference labels.",
  "label_source": "eval/results/reviewed_labels.json",
  "comparable_count": 80,
  "metrics": {
    "accuracy": 0.8875,
    "f1_macro": 0.8797704447632712,
    "f1_weighted": 0.8814992826398852,
    "precision_macro": 0.9100596760443308,
    "recall_macro": 0.869281045751634,
    "f1_per_category": {
      "accept": 0.9411764705882353,
      "reject": 0.9176470588235294,
      "needs_review": 0.7804878048780487
    },
    "confusion_matrix": [
      [
        16,
        0,
        1
      ],
      [
        0,
        39,
        0
      ],
      [
        1,
        7,
        16
      ]
    ]
  }
}
```

## RQ2

Completeness Agent missing-document detection.

```json
{
  "question": "Completeness Agent missing-document detection.",
  "label_source": "eval/results/reviewed_labels.json",
  "comparable_count": 80,
  "metrics": {
    "precision": 0.9523809523809523,
    "recall": 0.9523809523809523,
    "f1": 0.9523809523809523
  }
}
```

## RQ3

Quality Agent medical issue detection.

```json
{
  "question": "Quality Agent medical issue detection.",
  "label_source": "eval/results/reviewed_labels.json",
  "comparable_count": 80,
  "metrics": {
    "quality_issues": {
      "precision": 0.9423076923076923,
      "recall": 0.9607843137254902,
      "f1": 0.9514563106796117
    },
    "icd_detection": {
      "precision": 0.9298245614035088,
      "recall": 0.9636363636363636,
      "f1": 0.9464285714285715
    },
    "medication_detection": {
      "status": "computed",
      "precision": 0.9097744360902256,
      "recall": 0.983739837398374,
      "f1": 0.9453125000000001
    },
    "exclusion_detection": {
      "precision": 0.0,
      "recall": 0.0,
      "f1": 0.0
    },
    "consistency_issues": {
      "status": "computed",
      "precision": 0.9423076923076923,
      "recall": 0.9607843137254902,
      "f1": 0.9514563106796117
    }
  }
}
```

## RQ4

Trace, tool-call, and workflow adherence.

```json
{
  "question": "Trace, tool-call, and workflow adherence.",
  "metrics": {
    "routing_accuracy": 0.8125,
    "trace_completeness": 1.0,
    "tool_usage": {
      "status": "computed",
      "precision": 1.0,
      "recall": 0.029166666666666667,
      "f1": 0.056680161943319846
    },
    "invalid_tool_call_rate": 0.0,
    "tool_failure_rate": 0.0
  }
}
```

## RQ5

Multi-agent advantage over single-agent baseline.

```json
{
  "question": "Multi-agent advantage over single-agent baseline.",
  "status": "computed",
  "paired_count": 50,
  "multi_agent": {
    "accuracy": 0.82,
    "f1_macro": 0.773391812865497,
    "latency_mean_ms": 34261.387522459954,
    "avg_tokens_per_claim": 0.0
  },
  "single_agent": {
    "accuracy": 0.6,
    "f1_macro": 0.6098039215686275,
    "latency_mean_ms": 29863.215051619773,
    "avg_tokens_per_claim": 54261.04
  },
  "delta": {
    "accuracy": 0.21999999999999997,
    "f1_macro": 0.16358789129686946
  }
}
```

## Limitations

- Reference labels may be LLM-assisted and must be interpreted with their audit scope.
- OCR quality can affect both multi-agent and single-agent results.
- Tool-call metrics are reported as `not_observed` when trace data does not include tool calls.
- RQ5 is valid only for paired claims that share labels, OCR data, and model configuration.
