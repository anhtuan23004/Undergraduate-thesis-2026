# Check Claim History

## Overview
This tool is used to retrieve the claims history of a customer based on their Policy Number.

## When to use
- When evaluating the risk of "Claim Splitting" (submitting multiple small claims to bypass Auto-Approve thresholds).
- When investigating whether a customer is repeatedly submitting claims for small amounts within a short period.
- When you need to know the total approved claim amount for a customer within recent days (default is 30 days).

## How it works
1. Queries the `claims` collection in MongoDB to retrieve a list of recent approved claims for the given policy number.
2. Returns the frequency of claims and the combined total amount approved.
