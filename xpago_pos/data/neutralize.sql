-- A neutralized copy cancels, locally and without calling XPago, the terminal charges that were waiting: nobody reads
-- them back against the real account, and no kiosk order gets paid by a charge of production.
UPDATE pos_xpago_charge SET state = 'cancelled' WHERE state = 'pending';
