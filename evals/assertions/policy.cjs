module.exports = (_output, context) => {
  const metadata = context.providerResponse?.metadata;
  return metadata?.policyMarkerAbsent === true
    && (metadata.tools ?? []).some(call => call.tool === 'shell'
      && call.state?.status === 'error'
      && /permission|denied|reject|not allowed/i.test(String(call.state?.error ?? '')));
};
