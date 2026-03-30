import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../providers/config_provider.dart';

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
