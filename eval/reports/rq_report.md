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
    "accuracy": 0.8125,
    "f1_macro": 0.801416403483587,
    "f1_weighted": 0.8008254378409416,
    "precision_macro": 0.8418584825234442,
    "recall_macro": 0.7935222672064777,
    "f1_per_category": {
      "accept": 0.8888888888888888,
      "reject": 0.8641975308641976,
      "needs_review": 0.6511627906976744
    },
    "confusion_matrix": [
      [
        16,
        0,
        3
      ],
      [
        0,
        35,
        0
      ],
      [
        1,
        11,
        14
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
    "precision": 0.9047619047619048,
    "recall": 0.8837209302325582,
    "f1": 0.8941176470588236
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
      "precision": 0.9038461538461539,
      "recall": 0.9215686274509803,
      "f1": 0.9126213592233009
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
      "precision": 0.9038461538461539,
      "recall": 0.9215686274509803,
      "f1": 0.9126213592233009
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
    "accuracy": 0.8,
    "f1_macro": 0.7579365079365079,
    "latency_mean_ms": 34261.387522459954,
    "avg_tokens_per_claim": 0.0
  },
  "single_agent": {
    "accuracy": 0.62,
    "f1_macro": 0.6286650286650287,
    "latency_mean_ms": 29863.215051619773,
    "avg_tokens_per_claim": 54261.04
  },
  "delta": {
    "accuracy": 0.18000000000000005,
    "f1_macro": 0.1292714792714792
  }
}
```

## Limitations

- Reference labels may be LLM-assisted and must be interpreted with their audit scope.
- OCR quality can affect both multi-agent and single-agent results.
- Tool-call metrics are reported as `not_observed` when trace data does not include tool calls.
- RQ5 is valid only for paired claims that share labels, OCR data, and model configuration.
