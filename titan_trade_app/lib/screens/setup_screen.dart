import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../providers/config_provider.dart';

class SetupScreen extends ConsumerStatefulWidget {
  const SetupScreen({super.key});

  @override
  ConsumerState<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends ConsumerState<SetupScreen> {
  final _controller = TextEditingController(text: 'https://');
  String? _error;
  bool _loading = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _confirm() async {
    final url = _controller.text.trim().replaceAll(RegExp(r'/+$'), '');
    if (url.isEmpty || url == 'https:/') {
      setState(() => _error = 'Please enter the server URL.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    final valid = await validateBaseUrl(url);
    if (!mounted) return;
    if (!valid) {
      setState(() {
        _loading = false;
        _error = 'Could not reach $url/api/health — check the URL and try again.';
      });
      return;
    }
    await ref.read(baseUrlProvider.notifier).setUrl(url);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Welcome to TitanTrade', style: theme.textTheme.headlineMedium),
                  const SizedBox(height: 8),
                  Text(
                    'Enter the TitanTrade server URL to get started.',
                    style: theme.textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 24),
                  TextField(
                    controller: _controller,
                    decoration: InputDecoration(
                      labelText: 'Server URL',
                      hintText: 'https://trade.praguefun.cz',
                      errorText: _error,
                      border: const OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _confirm(),
                  ),
                  const SizedBox(height: 24),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton(
                      onPressed: _loading ? null : _confirm,
                      child: _loading
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Connect'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
