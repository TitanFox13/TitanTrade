import 'package:file_picker/file_picker.dart';
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
  late TextEditingController _pathController;
  String? _pathError;
  String? _pathSuccess;

  static const _refreshOptions = [10, 15, 30, 60, 120];

  @override
  void initState() {
    super.initState();
    final currentPath = ref.read(dataPathProvider).valueOrNull ?? '';
    _pathController = TextEditingController(text: currentPath);
  }

  @override
  void dispose() {
    _pathController.dispose();
    super.dispose();
  }

  Future<void> _browse() async {
    final result = await FilePicker.platform.getDirectoryPath(
      dialogTitle: 'Select TitanTrade directory',
    );
    if (result != null) {
      _pathController.text = result;
      setState(() {
        _pathError = null;
        _pathSuccess = null;
      });
    }
  }

  Future<void> _updatePath() async {
    final path = _pathController.text.trim();
    if (path.isEmpty) {
      setState(() => _pathError = 'Path cannot be empty');
      return;
    }
    if (!validateDataPath(path)) {
      setState(() => _pathError = 'Invalid: state/portfolio.json not found');
      return;
    }
    await ref.read(dataPathProvider.notifier).setPath(path);
    setState(() {
      _pathError = null;
      _pathSuccess = 'Data path updated';
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final currentPath = ref.watch(dataPathProvider).valueOrNull ?? '';
    final refreshSeconds = ref.watch(refreshIntervalProvider);

    return Scaffold(
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text('Settings', style: theme.textTheme.headlineMedium),
          const SizedBox(height: 24),

          // ---- Data Path ----
          Text('Data Path', style: theme.textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(
            'The TitanTrade project directory containing state/ and data/ folders.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _pathController,
                  decoration: InputDecoration(
                    labelText: 'TitanTrade directory',
                    errorText: _pathError,
                    helperText: _pathSuccess,
                    border: const OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              IconButton.filled(
                onPressed: _browse,
                icon: const Icon(Icons.folder_open),
                tooltip: 'Browse',
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: _updatePath,
                child: const Text('Apply'),
              ),
            ],
          ),
          if (currentPath.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('Current: $currentPath', style: theme.textTheme.bodySmall),
          ],
          const SizedBox(height: 32),

          // ---- Refresh Interval ----
          Text('Refresh Interval', style: theme.textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(
            'How often the app polls state files for updates.',
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
