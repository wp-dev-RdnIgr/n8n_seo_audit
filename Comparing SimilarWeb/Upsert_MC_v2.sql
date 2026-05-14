SELECT upsert_similarweb_data(
  p_client_site    := '{{ $json.client_site }}',
  p_site           := '{{ $json.site }}',
  p_site_type      := '{{ $json.type }}',
  p_period         := '{{ $json.period }}',
  p_direct         := '{{ $json.Direct }}',
  p_organic_search := '{{ $json["Organic Search"] }}',
  p_paid_search    := '{{ $json["Paid Search"] }}',
  p_display_ads    := '{{ $json["Display Ads"] }}',
  p_social_organic := '{{ $json["Social Organic"] }}',
  p_social_paid    := '{{ $json["Social Paid"] }}',
  p_email          := '{{ $json.Email }}',
  p_affiliates     := '{{ $json.Affiliates }}',
  p_gen_ai         := '{{ $json["Gen AI"] }}',
  p_task_id        := '{{ $json["Task ID"] }}',
  p_queue_id       := '{{ $json["Queue ID"] }}'
);
