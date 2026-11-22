# Process recovery method

Read retained ownership, collector and queue receipts. Submission is not completion.
Use status for the owned lab attempt. Recover only a terminal attempt; the host
checks task ownership and reconciles exact nonce/name/image/CID intent. Active
work must use lab_client.cancel. Missing final records remain partial failure.
The guardian retains exclusion until orphan cleanup. Do not infer reboot/power-loss
recovery, semantic correctness or performance benefit from process cleanup.
