$(function() {
	var valueChangingKeys = {
		'Backspace': 1,
		'Delete': 1,
		'+': 1,
		'-': 1,
		'0': 1,
		'1': 1,
		'2': 1,
		'3': 1,
		'4': 1,
		'5': 1,
		'6': 1,
		'7': 1,
		'8': 1,
		'9': 1,
		'.': 1,
	};

	function onlyNumericKeys(eventHandler) { // Run an event handler only on keyboard events
		return function(ev) { //  that change numeric inputs
			if (ev && 'key' in ev && ev.key in valueChangingKeys) {
				eventHandler.apply(this, [ev])
			}
		}
	};
	withCountries(function() {
		$.getJSON("/authentication", function(auth) {
			var anyCountry = [{
					Code: "any",
					Id: NaN,
					Flag_Image: ""
				}],
				lastDatesItemEdited = null,
				selectedPlayers = new Object(), // hash of selected Player Id's
				createPlayerSelectButton = function(editable) {
					return function(value, item) {
						var box = this._createCheckbox().prop({
							checked: item.Id && selectedPlayers[item.Id],
							disabled: !editable
						});
						if (editable) {
							box.click(function(e) {
								selectedPlayers[item.Id] = $(this).prop("checked");
								players = selectedPlayerIDs();
								e.stopPropagation();
							})
						};
						return box;
					}
				},
				tournamentFieldWidth = 150,
				tournamentFieldDescriptions = [{
						name: "Id",
						type: "number",
						visible: false
					},
					{
						name: "Name",
						type: "text",
						inserting: auth['user'],
						editing: auth['user'],
						validate: "required",
						itemTemplate: tournamentLinkTemplate,
						css: "tourneynamefield",
						width: tournamentFieldWidth * 2,
					},
					{
						name: "Dates",
						type: "text",
						inserting: auth['user'],
						editing: auth['user'],
						itemTemplate: datesTemplate,
						editTemplate: datesEditTemplate,
						insertTemplate: datesEditTemplate,
						insertValue: function() {
							return datesValue(this.insertControl)
						},
						editValue: function() {
							return datesValue(this.editControl)
						},
						css: "tourneydatesfield",
						width: tournamentFieldWidth,
					},
					{
						name: "Location",
						type: "text",
						inserting: auth['user'],
						editing: auth['user'],
						css: "tourneylocationfield",
						width: tournamentFieldWidth,
					},
					{
						name: "Country",
						type: "select",
						items: anyCountry.concat(countryList),
						inserting: auth['user'],
						editing: auth['user'],
						css: "tourneycountryfield",
						valueField: "Id",
						valueType: "number",
						textField: "Code",
						itemTemplate: countryTemplate,
						width: tournamentFieldWidth,
					},
					{
						name: "Players",
						type: "text",
						editing: false,
						inserting: false,
						itemTemplate: playerSummaryTemplate,
						sorting: false,
						filtering: false,
						css: "playersummaryfield",
						width: tournamentFieldWidth,
					},
					{
						type: "control",
						itemTemplate: function(value, item) {
							var $result = $([]);
							if (auth['user']) {
								var editOK = (auth['admin'] || auth['user'] == item.Owner);
								if (this.editButton && editOK) {
									$result = $result.add(
										this._createEditButton(item));
								}
								if (this.deleteButton && editOK) {
									$result = $result.add(
										this._createDeleteButton(item));
								}
								if (auth['user']) {
									$result = $result.add(createDuplicateButton(
										item, duplicateTournament, 'tournament'));
								}
							}
							return $result;
						},
						css: "tourneycontrolfield",
						width: tournamentFieldWidth * 3 / 4,
					}
				],
				tournamentsGridController = makeController(base + "tournamentList",
					tournamentFieldDescriptions),
				switchedtourneyfieldselectors = [],
				//				'.tourneylocationfield', '.tourneycontrolfield'],

				playerTypes = [],
				playerGridFieldWidth = 50,
				tourneyPlayerGridFields = [{
						name: "Id",
						type: "number",
						visible: false
					},
					{
						name: "Type",
						type: "select",
						css: "playertypefield",
						items: playerTypes,
						inserting: false,
						editing: false,
						filtering: false,
						valueField: "Id",
						valueType: "number",
						textField: "Type",
						itemTemplate: playerTypeTemplate,
						width: playerGridFieldWidth,
					},
					{
						name: "Name / Association",
						type: "text",
						inserting: false,
						editing: false,
						itemTemplate: playerNameAssociationTemplate,
						css: "playernameassociationfield",
						width: playerGridFieldWidth * 2,
					},
					{
						name: "Number",
						title: "#",
						type: "number",
						inserting: false,
						editing: false,
						css: "playernumberfield",
						itemTemplate: makePlayerFieldTemplate('Number', true),
						width: playerGridFieldWidth,
					},
					{
						name: "Pool",
						type: "text",
						inserting: false,
						editing: false,
						css: "playerpoolfield",
						itemTemplate: makePlayerFieldTemplate('Pool', false),
						width: playerGridFieldWidth,
					},
					{
						name: "Wheel",
						type: "number",
						inserting: false,
						editing: false,
						css: "playerwheelfield",
						itemTemplate: makePlayerFieldTemplate('Wheel', true),
						width: playerGridFieldWidth,
					},
					{
						name: "",
						type: "checkbox",
						width: "2em",
						inserting: false,
						editing: false,
						filtering: false,
						css: "playerselectboxfield",
						itemTemplate: createTourneyPlayerSelectButton(true),
						visible: auth['user'],
					},
				],
				tourneyPlayers = null,
				selectedTourneyPlayers = null,
				tourneyPlayerGridController = null;

			function createTourneyPlayerSelectButton(enable) {
				return function(value, item) {
					var box = this._createCheckbox().prop({
						checked: false,
					});
					if (enable) {
						box.click(function(e) {
							selectedTourneyPlayers[item.Id] = $(this).prop("checked");
							e.stopPropagation();
						})
					};
					return box;
				}
			};

			function selectedPlayerIDs() {
				var playerlist = [];
				for (p in selectedPlayers) {
					if (selectedPlayers[p]) {
						playerlist.push(p)
					}
				};
				return playerlist;
			};

			function clearSelectedPlayers() {
				for (p in selectedPlayers) {
					delete selectedPlayers[p]
				};
				$("#playersGrid .PlayerSelectBox input").prop("checked", false);
			};

			function datesTemplate(value, item) {
				return item.Start + ' - ' + item.End;
			};

			function datesEditTemplate(value, item) {
				var fields = ['Start', 'End'],
					forInsert = value === undefined && item === undefined,
					dom = $('<div class="datepair">')
					.append('<span class="fieldlabel">Start:</span>')
					.append('<input class="startdate" type="text">')
					.append('<span class="fieldlabel">End:</span>')
					.append('<input class="enddate" type="text">')
				dom.find('input').each(function(i, field) {
					$(field).val(item && item[fields[i]] ? item[fields[i]] : null)
						.datepicker({
							dateFormat: "yy-mm-dd",
							showAnim: "slideDown",
							changeMonth: true,
							changeYear: true,
							defaultDate: i > 0 ? "+1d" : null,
						});
				});
				this[forInsert ? 'insertControl' : 'editControl'] = dom
				lastDatesItemEdited = item;
				return dom;
			};

			function datesValue(control) {
				var start = $(control).find("input.startdate").val(),
					end = $(control).find("input.enddate").val();
				if (start && end && lastDatesItemEdited &&
					'Start' in lastDatesItemEdited &&
					'End' in lastDatesItemEdited) {
					lastDatesItemEdited.Start = start;
					lastDatesItemEdited.End = end;
				};
				return start + ' - ' + end;
			};

			function tournamentItemInserting(obj) {
				var dateparts = obj.item.Dates && obj.item.Dates.split(' - ');
				if (dateparts && dateparts.length == 2) {
					obj.item.Start = dateparts[0];
					obj.item.End = dateparts[1];
				}
			};

			function playerSummaryTemplate(value, item) {
				var viewControl = $('<span class="playerviewcontrol jsgrid-button">')
					.data('tourney', item).text('▶').click(togglePlayerView),
					summary = playerTypeSummary(item.players);
				return $('<span class="playersummary">')
					.data('item', item).data('tourneyid', item.Id)
					.text(summary).prepend(viewControl);
			};

			function playerTypeSummary(players) {
				var summary = '';
				for (type in players) {
					if (players[type].length > 0) {
						if (summary.length > 0) {
							summary += ', '
						};
						summary += players[type].length + ' ' + type;
					}
				}
				return summary.length == 0 ? "none" : summary;
			}

			function playerTypeTemplate(value, item) {
				var selector = $('<select class="playertypeselector">')
					.data('field', 'Type').data('item', item)
					.change(playerFieldChange);
				playerTypes.map(function(entry) {
					$("<option>").attr("value", entry.Id).text(entry.Type)
						.prop("selected", value == entry.Id).appendTo(selector);
				});
				return selector;
			};

			function makePlayerFieldTemplate(field, numeric) {
				return function(value, item) {
					if (auth['admin'] || auth['user'] == item.Owner) {
						return $('<input>').attr('type', numeric ? 'number' : 'text').val(value)
							.attr('size', 5).data('field', field).data('item', item)
							.change(playerFieldChange).keyup(
								numeric ? onlyNumericKeys(playerFieldChange) : playerFieldChange)
					}
					else {
						return value
					}
				}
			};

			function playerFieldChange(ev) {
				var etype = ev && 'type' in ev && ev.type,
					control = $(this),
					field = $(this).data('field'),
					item = $(this).data('item');
				$.post(base + 'updatePlayerRole', {
						update: JSON.stringify({
							'item': item,
							'field': field,
							'value': control.val(),
						})
					},
					function(resp) {
						if (resp.status != 0) {
							$.notify(resp.message);
							control.addClass('bad');
						}
						else {
							control.removeClass('bad');
							updateItemField(item, field, control.val(), control);
						}
					});
			};

			function updateItemField(item, field, value, control) {
				item[field] = value;
				if (field == 'Type') { // For updates to player type, find and redo the type summary
					$('#tournamentsgrid .playersummary').each(function(i, elem) {
						if ($(elem).data('tourneyid') == item.Tournament) {
							var players = $(elem).data('item').players;
							for (type in players) {
								for (j = 0; j < players[type].length; j++) {
									if (players[type][j].Id == item.Id) {
										break
									}
								}
								if (j < players[type].length) {
									players[type].splice(j, 1)
								}
							};
							players[playerTypes[value - 0].Type].push(item);
							$(elem).text(playerTypeSummary(players));
						}
					});
				}
			};

			function playerNameAssociationTemplate(value, item) {
				var playerStatLink = $('<a>')
					.attr('href', base + 'playerStats/' + item.Id)
					.text(item.Name);
				return $('<span>').text(item.Association ? ' / ' + item.Association : '')
					.prepend(playerStatLink);
			};

			function togglePlayerView(ev) {
				var on = $(this).hasClass('view-on');
				clearPlayerViews(this);
				if (!on) {
					$(this).addClass('view-on').text('▼');
					showPlayerView(this)
				};
				ev.stopPropagation();
			};

			function clearPlayerViews(button) {
				$(button).parents('#tournamentsgrid').find('.playerviewcontrol')
					.filter('.view-on').removeClass('view-on').text('▶');
				$('.tourneyplayersrow').remove();
				$('#transferplayersbutton, #playerspanel').hide();
				$(switchedtourneyfieldselectors.join(', ')).show();
				$('#tournamentspanel').removeClass('tournamentplayereditmode');
			}

			function showPlayerView(button) {
				var tourneyRow = $(button).parents('tr').first(),
					tourney = $(button).data('tourney'),
					playerList = [];
				if (auth['admin'] || auth['user'] == tourney.Owner) {
					$('#transferplayersbutton, #playerspanel').show().removeClass('hidden');
					$(switchedtourneyfieldselectors.join(', ')).hide();
					$('#tournamentspanel, #playerspanel').addClass('tournamentplayereditmode');
				}
				tourneyPlayers = new Object();
				playerTypes = []; // NOTE: Assume entries in players are always in numeric order
				for (type in tourney.players) {
					playerTypes.push({
						'Type': type,
						'Id': playerTypes.length
					});
					tourney.players[type].map(function(player) {
						tourneyPlayers[player.Id] = 1;
						playerList.push(player);
					});
				};
				selectedTourneyPlayers = new Object();
				var grid = $('<div id="tourneyplayers" class="tourneyplayersgrid">').jsGrid({
						width: '90%',
						inserting: false,
						editing: false,
						sorting: true,
						filtering: true,
						data: playerList,
						paging: false,
						pageLoading: false,
						// controller: tourneyPlayerGridController,
						fields: tourneyPlayerGridFields,
						noDataContent: 'None found',
					}),
					label = $('<div class="sidelabelwrapper">').text('Players'),
					cell = $('<td>').attr('colspan', tournamentFieldDescriptions.filter(
						function(field) {
							return field.visible != false
						}).length).append(label).append(grid),
					innerRow = $('<tr class="tourneyplayersrow">')
					.addClass($(tourneyRow).hasClass('jsgrid-alt-row') ?
						'jsgrid-row' : 'jsgrid-alt-row').append(cell);
				$(tourneyRow).after(innerRow);
			}

			function duplicateTournament(e) {
				var tourneyID = $(this).data('tourneyid');
				$.notify('Duplicate tournament ' + tourneyID);
				e.stopPropagation();
			};

			$("#tournamentsgrid").text('').jsGrid({
				height: "auto",
				inserting: auth['user'] ? true : false,
				editing: auth['user'] ? true : false,
				sorting: true,
				filtering: true,
				autoload: true,
				paging: false,
				pageLoading: false,
				deleteConfirm: 'Are you sure you want to delete this tournament?',
				noDataContent: 'None found',
				controller: tournamentsGridController,
				fields: tournamentFieldDescriptions,
				onItemInserting: tournamentItemInserting,
				onItemEditing: tournamentItemInserting,
			});
		});
	});
});
