import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../providers/config_provider.dart';
import '../providers/trading_mode_provider.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late TextEditingController _urlController;
  String? _urlError;
  String? _urlSuccess;
  bool _validating = false;

  static const _refreshOptions = [10, 15, 30, 60, 120];

  @override
  void initState() {
    super.initState();
    final currentUrl = ref.read(baseUrlProvider).valueOrNull ?? '';
    _urlController = TextEditingController(text: currentUrl);
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _updateUrl() async {
    final url = _urlController.text.trim().replaceAll(RegExp(r'/+$'), '');
    if (url.isEmpty) {
      setState(() => _urlError = 'URL cannot be empty');
      return;
    }
    setState(() {
      _validating = true;
      _urlError = null;
      _urlSuccess = null;
    });
    final valid = await validateBaseUrl(url);
    if (!mounted) return;
    if (!valid) {
      setState(() {
        _validating = false;
        _urlError = 'Could not reach $url/api/health';
      });
      return;
    }
    await ref.read(baseUrlProvider.notifier).setUrl(url);
    setState(() {
      _validating = false;
      _urlSuccess = 'Server URL updated';
    });
  }

  Future<void> _toggleTradingMode(bool enableLive) async {
    if (enableLive) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Enable Live Trading?'),
          content: const Text(
            'This will execute real trades with real money. '
            'Make sure you understand the risks before proceeding.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: Colors.red,
              ),
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const Text('Enable Live Trading'),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
    }
    await ref
        .read(tradingModeProvider.notifier)
        .setMode(enableLive ? 'live' : 'paper');
  }

  Widget _buildTradingModeSection(ThemeData theme) {
    final modeAsync = ref.watch(tradingModeProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Trading Mode', style: theme.textTheme.titleLarge),
        const SizedBox(height: 4),
        Text(
          'Switch between paper (simulated) and live (real money) trading.',
          style: theme.textTheme.bodySmall,
        ),
        const SizedBox(height: 12),
        modeAsync.when(
          loading: () => const SizedBox(
            height: 48,
            child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
          ),
          error: (_, __) => Text(
            'Could not load trading mode from server.',
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.error),
          ),
          data: (modeState) {
            final canToggle = modeState.liveKeysConfigured;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    modeState.isLive ? 'LIVE TRADING' : 'Paper Trading',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: modeState.isLive ? Colors.red : null,
                    ),
                  ),
                  subtitle: Text(
                    canToggle
                        ? (modeState.isLive
                            ? 'Trading with real money via Alpaca'
                            : 'Using simulated paper account')
                        : 'Live keys not configured in .env',
                  ),
                  value: modeState.isLive,
                  onChanged: canToggle ? _toggleTradingMode : null,
                ),
              ],
            );
          },
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final currentUrl = ref.watch(baseUrlProvider).valueOrNull ?? '';
    final refreshSeconds = ref.watch(refreshIntervalProvider);

    return Scaffold(
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text('Settings', style: theme.textTheme.headlineMedium),
          const SizedBox(height: 24),

          // ---- Server URL ----
          Text('Server URL', style: theme.textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(
            'The TitanTrade backend URL (e.g. https://trade.praguefun.cz).',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _urlController,
                  decoration: InputDecoration(
                    labelText: 'Server URL',
                    errorText: _urlError,
                    helperText: _urlSuccess,
                    border: const OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => _updateUrl(),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: _validating ? null : _updateUrl,
                child: _validating
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Apply'),
              ),
            ],
          ),
          if (currentUrl.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('Current: $currentUrl', style: theme.textTheme.bodySmall),
          ],
          const SizedBox(height: 32),

          // ---- Trading Mode ----
          _buildTradingModeSection(theme),
          const SizedBox(height: 32),

          // ---- Refresh Interval ----
          Text('Refresh Interval', style: theme.textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(
            'How often the app polls the server for updates.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            children: _refreshOptions.map((seconds) {
              final selected = seconds == refreshSeconds;
              return ChoiceChip(
                label: Text('${seconds}s'),
                selected: selected,
                onSelected: (val) {
                  if (val) ref.read(refreshIntervalProvider.notifier).set(seconds);
                },
              );
            }).toList(),
          ),
          const SizedBox(height: 8),
          Text(
            'Currently polling every $refreshSeconds seconds.',
            style: theme.textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
