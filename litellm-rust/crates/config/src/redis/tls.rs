use litellm_redis_types::TlsOptions;

use super::{
    Expected, RedisError,
    keys::Ignored,
    layers::Entry,
    options::{TlsInput, flag, parsed, text},
};
use crate::Value;

// redis-py's parse_url turns every query parameter into a client kwarg. Only the TLS ones have a redis-rs
// equivalent, so any other parameter, and any parameter on a plain redis:// url, is ignored
const URL_TLS_SETTINGS: &[&str] = &[
    "ssl_cert_reqs",
    "ssl_ca_certs",
    "ssl_ca_data",
    "ssl_ca_path",
    "ssl_certfile",
    "ssl_keyfile",
    "ssl_check_hostname",
];

/// `gcp_ca_certs` replaces `ssl_ca_certs` when GCP IAM is on, as `_get_redis_client_logic` does.
pub(super) fn tls_options(
    input: &TlsInput,
    gcp_ca_certs: Option<&Entry>,
) -> Result<TlsOptions, RedisError> {
    Ok(TlsOptions {
        ca_certs: text(gcp_ca_certs.or(input.ca_certs.as_ref())).map(Into::into),
        ca_data: text(input.ca_data.as_ref()),
        ca_path: text(input.ca_path.as_ref()).map(Into::into),
        certfile: text(input.certfile.as_ref()).map(Into::into),
        keyfile: text(input.keyfile.as_ref()).map(Into::into),
        verify_certificate: verify_certificate(input.cert_reqs.as_ref())?,
        check_hostname: flag(input.check_hostname.as_ref())?,
    })
}

fn verify_certificate(cert_reqs: Option<&Entry>) -> Result<bool, RedisError> {
    parsed(cert_reqs, Expected::CertRequirement, |text| match text {
        "required" | "optional" => Some(true),
        "none" => Some(false),
        _ => None,
    })
    .map(|verify| verify.unwrap_or(true))
}

pub(super) fn url_tls(url: &str) -> Result<(TlsOptions, Vec<Ignored>), RedisError> {
    let Ok(parsed) = url::Url::parse(url) else {
        return Ok((TlsOptions::verified(), Vec::new()));
    };
    let tls_scheme = parsed.scheme().eq_ignore_ascii_case("rediss");
    let query: Vec<(String, Entry)> = parsed
        .query_pairs()
        .map(|(name, value)| {
            (
                name.to_string(),
                Entry {
                    value: Value::String(value.into_owned()),
                    source: format!("url ?{name}"),
                },
            )
        })
        .collect();
    let (query, ignored): (Vec<_>, Vec<_>) = query
        .into_iter()
        .partition(|(name, _)| tls_scheme && URL_TLS_SETTINGS.contains(&name.as_str()));
    let ignored = ignored
        .into_iter()
        .map(|(name, entry)| Ignored::new(entry.source, &name))
        .collect();
    let get = |key: &str| {
        query
            .iter()
            .rev()
            .find(|(name, _)| name == key)
            .map(|(_, entry)| entry.clone())
    };
    let tls = TlsOptions {
        ca_certs: text(get("ssl_ca_certs").as_ref()).map(Into::into),
        ca_data: text(get("ssl_ca_data").as_ref()),
        ca_path: text(get("ssl_ca_path").as_ref()).map(Into::into),
        certfile: text(get("ssl_certfile").as_ref()).map(Into::into),
        keyfile: text(get("ssl_keyfile").as_ref()).map(Into::into),
        verify_certificate: verify_certificate(get("ssl_cert_reqs").as_ref())?,
        check_hostname: text(get("ssl_check_hostname").as_ref())
            .is_some_and(|text| url_bool(&text)),
    };
    Ok((tls, ignored))
}

// redis-py's to_bool: only 0, F, FALSE, N and NO (any case) are false
fn url_bool(text: &str) -> bool {
    !matches!(
        text.to_ascii_uppercase().as_str(),
        "" | "0" | "F" | "FALSE" | "N" | "NO"
    )
}
