-- How each activity is booked is found at collection (surprise.booking, the activity's `booking`): free, a slot
-- an engine tells for a date, a ticketing, or no booking. For a slot, the engine and the activity's id there
-- ("zenchef:351778"), so that an evening asks the engine at once, without reading the venue's site again.
-- A page's verdict keeps that id too.
alter table pipeline.page_checks add column if not exists slot_check text;

-- The pages of a widget engine were checked without their venue's id: read again once (surprise.renormalize).
delete from pipeline.page_checks where engine in ('Zenchef', 'SevenRooms', '4escape');
