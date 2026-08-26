{ pkgs, ... }:
{
  imports = [ ./modules/pi-agent.nix ];

  piAgent = {
    settings = {
      defaultProvider = "openrouter";
      defaultModel = "stealth/ox-alpha";
      defaultThinkingLevel = "xhigh";
    };

    models.providers.openrouter.models = [
      {
        id = "stealth/ox-alpha";
        name = "Ox Alpha (free via OpenRouter)";
        reasoning = true;
        thinkingLevelMap = {
          off = null;
          minimal = null;
          medium = null;
          xhigh = "max";
        };
        input = [
          "text"
          "image"
        ];
        contextWindow = 1048576;
        maxTokens = 131072;
        cost = {
          input = 0;
          output = 0;
          cacheRead = 0;
          cacheWrite = 0;
        };
      }
    ];
  };

  packages = [
    pkgs.secretspec
  ];
}
