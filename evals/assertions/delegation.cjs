module.exports = (_output, context) => {
  const calls = context.providerResponse?.metadata?.tools ?? [];
  return calls.some(call => call.tool === 'subagent'
    && call.state?.status === 'completed'
    && JSON.stringify(call.state?.input ?? {}).includes('security-reviewer')
    && /SQL injection/i.test(String(call.state?.output ?? '')));
};
