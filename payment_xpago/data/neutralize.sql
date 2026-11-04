-- a neutralized copy must never charge with the real XPago account
UPDATE payment_provider SET xpago_api_key = NULL WHERE code = 'xpago';
