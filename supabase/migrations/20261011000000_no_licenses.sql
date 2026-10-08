-- The sources' images and texts carry no licence any more: none kept on a source, nor on an image (the check that an
-- image had one goes with its column).
alter table public.sources drop column if exists license;
alter table public.activities drop column if exists image_license;
