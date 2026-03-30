import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../models/backtest_result.dart';
import '../providers/config_provider.dart';
import '../theme.dart';

class BacktestScreen extends ConsumerStatefulWidget {
  const BacktestScreen({super.key});

  @override
  ConsumerState<BacktestScreen> createState() => _BacktestScreenState();
}

class _BacktestScreenState extends ConsumerState<BacktestScreen> {
  String? _downloadJobId;
  String? _backtestJobId;
  String? _analyzeJobId;

  String _downloadStatus = '';
  String _backtestStatus = '';
  String _analyzeStatus = '';

  BacktestResult? _result;
  bool _loadingResult = false;

  String get _baseUrl => ref.read(baseUrlProvider).valueOrNull ?? '';

  @override
  void initState() {
    super.initState();
    _loadExistingResults();
  }

  Future<void> _loadExistingResults() async {
    if (_baseUrl.isEmpty) return;
    setState(() => _loadingResult = true);
    try {
      final resp = await http.get(Uri.parse('$_baseUrl/api/backtest-results'));
      if (resp.statusCode == 200) {
        setState(() => _result = BacktestResult.fromJson(jsonDecode(resp.body)));
      }
    } catch (_) {}
    setState(() => _loadingResult = false);
  }

  Future<void> _triggerAction(String action, void Function(String jobId) setJobId, void Function(String status) setStatus) async {
    try {
      setStatus('Starting...');
      final resp = await http.post(Uri.parse('$_baseUrl/api/actions/$action'));
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body);
        final jobId = data['job_id'] as String;
        setJobId(jobId);
        _pollJob(jobId, setStatus, action == 'backtest');
      } else {
        setStatus('Failed to start: ${resp.statusCode}');
      }
    } catch (e) {
      setStatus('Error: $e');
    }
  }

  Future<void> _pollJob(String jobId, void Function(String) setStatus, bool loadResultOnComplete) async {
    while (mounted) {
      await Future.delayed(const Duration(seconds: 2));
      try {
        final resp = await http.get(Uri.parse('$_baseUrl/api/jobs/$jobId'));
        if (resp.statusCode == 200) {
          final data = jsonDecode(resp.body);
          final status = data['status'] as String;
          if (status == 'completed') {
            setStatus('Completed');
            if (loadResultOnComplete) _loadExistingResults();
            return;
          } else if (status == 'failed') {
            setStatus('Failed: ${data['error'] ?? 'Unknown error'}');
            return;
          } else {
            setStatus('Running...');
          }
        }
      } catch (_) {}
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text('Backtest & Analysis', style: theme.textTheme.headlineSmall),
          const SizedBox(height: 24),

          // --- Actions ---
          Text('Actions', style: theme.textTheme.titleLarge),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              _ActionButton(
                icon: Icons.cloud_download,
                label: 'Download History',
                status: _downloadStatus,
                onPressed: () => _triggerAction(
                  'download-history',
                  (id) => setState(() => _downloadJobId = id),
                  (s) => setState(() => _downloadStatus = s),
                ),
              ),
              _ActionButton(
                icon: Icons.speed,
                label: 'Run Backtest',
                status: _backtestStatus,
                onPressed: () => _triggerAction(
                  'backtest',
                  (id) => setState(() => _backtestJobId = id),
                  (s) => setState(() => _backtestStatus = s),
                ),
              ),
              _ActionButton(
                icon: Icons.psychology,
                label: 'Run Analysis Now',
                status: _analyzeStatus,
                onPressed: () => _triggerAction(
                  'analyze',
                  (id) => setState(() => _analyzeJobId = id),
                  (s) => setState(() => _analyzeStatus = s),
                ),
              ),
            ],
          ),
          const SizedBox(height: 32),

          // --- Backtest Results ---
          Text('Backtest Results', style: theme.textTheme.titleLarge),
          const SizedBox(height: 12),
          if (_loadingResult)
            const Center(child: CircularProgressIndicator())
          else if (_result == null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Text('No backtest results yet. Download history then run a backtest.',
                    style: theme.textTheme.bodyMedium),
              ),
            )
          else
            _BacktestResultCard(result: _result!),
        ],
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final String status;
  final VoidCallback onPressed;

  const _ActionButton({
    required this.icon,
    required this.label,
    required this.status,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final isRunning = status == 'Running...' || status == 'Starting...';
    return SizedBox(
      width: 200,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              FilledButton.icon(
                onPressed: isRunning ? null : onPressed,
                icon: isRunning
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : Icon(icon),
                label: Text(label),
              ),
              if (status.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  status,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: status.startsWith('Failed') || status.startsWith('Error')
                        ? Colors.redAccent
                        : status == 'Completed'
                            ? Colors.greenAccent
                            : null,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _BacktestResultCard extends StatelessWidget {
  final BacktestResult result;

  const _BacktestResultCard({required this.result});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final m = result.metrics;
    final c = result.config;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${c.startDate ?? "?"} to ${c.endDate ?? "?"} (${c.tradingDays} days)',
                style: theme.textTheme.bodySmall),
            Text('${c.tickers.length} tickers, \$${c.initialCapital.toStringAsFixed(0)} capital',
                style: theme.textTheme.bodySmall),
            const Divider(height: 24),
            _MetricRow('Total Return', '${m.totalReturnPct >= 0 ? "+" : ""}${m.totalReturnPct.toStringAsFixed(1)}%',
                color: m.totalReturnPct >= 0 ? Colors.greenAccent : Colors.redAccent),
            _MetricRow('SPY Return', '${m.spyReturnPct >= 0 ? "+" : ""}${m.spyReturnPct.toStringAsFixed(1)}%'),
            _MetricRow('Alpha', '${m.alphaPct >= 0 ? "+" : ""}${m.alphaPct.toStringAsFixed(1)}%',
                color: m.alphaPct >= 0 ? Colors.greenAccent : Colors.redAccent),
            _MetricRow('Final Value', '\$${m.finalValue.toStringAsFixed(0)}'),
            const Divider(height: 16),
            _MetricRow('Trades', '${m.totalTrades}'),
            _MetricRow('Win Rate', '${m.winRate.toStringAsFixed(0)}%'),
            _MetricRow('Avg Win', '+${m.avgWinPct.toStringAsFixed(1)}%'),
            _MetricRow('Avg Loss', '${m.avgLossPct.toStringAsFixed(1)}%'),
            _MetricRow('Profit Factor', m.profitFactor.toStringAsFixed(2)),
            const Divider(height: 16),
            _MetricRow('Max Drawdown', '${m.maxDrawdownPct.toStringAsFixed(1)}% (${m.maxDrawdownDays}d)'),
            _MetricRow('Sharpe', m.sharpeRatio.toStringAsFixed(2)),
            _MetricRow('Sortino', m.sortinoRatio.toStringAsFixed(2)),
            _MetricRow('Avg Hold', '${m.avgHoldingDays.toStringAsFixed(0)} days'),
            if (m.exitTriggers.isNotEmpty) ...[
              const Divider(height: 16),
              Text('Exit Triggers', style: theme.textTheme.titleSmall),
              const SizedBox(height: 4),
              ...m.exitTriggers.entries.map(
                (e) => _MetricRow(e.key.replaceAll('_', ' '), '${e.value}'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _MetricRow extends StatelessWidget {
  final String label;
  final String value;
  final Color? color;

  const _MetricRow(this.label, this.value, {this.color});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: theme.textTheme.bodyMedium),
          Text(value, style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: color,
          )),
        ],
      ),
    );
  }
}
