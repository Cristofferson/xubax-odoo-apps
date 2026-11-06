-- A neutralized copy (a test database made from production) must never charge with the real XPago account, nor read
-- back or finish anything that was waiting on it: no key, provider off, the copy says so on the provider, and what
-- was waiting is cancelled here, locally, without calling XPago.
UPDATE payment_provider
   SET xpago_api_key = NULL, state = 'disabled', xpago_neutralized = TRUE
 WHERE code = 'xpago';
UPDATE payment_transaction
   SET state = 'cancel', state_message = 'Copia neutralizada: cancelada sin llamar a XPago.'
 WHERE state IN ('draft', 'pending', 'authorized')
   AND provider_id IN (SELECT id FROM payment_provider WHERE code = 'xpago');
DELETE FROM payment_xpago_connection;
