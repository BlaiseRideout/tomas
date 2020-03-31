(function() {
	updateFlagImage = function(updateObj, countries) {
		var country = countries.find( // Find country ID in countries array
			function(country) {
				return country.Id == updateObj.item.Country
			});
		if (country) {
			updateObj.item['Flag'] = country.Flag_Image;
			$(updateObj.row).find("td.FlagImage").html(country.Flag_Image);
		}
	};

	makeFilter = function(filterItem, fieldDescriptions) {
		return function(item) { // Create a function to filter items based on
			var keep = true; // user's filter parameters and field types
			for (field in fieldDescriptions) {
				var fd = fieldDescriptions[field];
				if (filterItem[fd.name] && ( // Only check visible fields
						!fd.hasOwnProperty("visible") || fd.visible)) {
					if ((["number", "checkbox", "select"].indexOf(fd.type) > -1 &&
							item[fd.name] != filterItem[fd.name]) ||
						(fd.type == "text" && item[fd.name] &&
							item[fd.name].toLowerCase().indexOf(
								filterItem[fd.name].toLowerCase()) == -1)) {
						keep = false;
						break; // Once a filter fails, quit loop
					}
				}
			};
			return keep
		}
	};

	function postItemChange(jsonURL, item, deferred) {
		$.post(jsonURL, {
				item: JSON.stringify(item)
			},
			function(resp) {
				if (resp.status != 0) {
					$.notify(resp.message)
					deferred.reject(resp.item);
				}
				else {
					deferred.resolve(resp.item);
				}
			}, "json");
	};

	makeController = function(jsonURL, fieldDescriptions) {
		return { // Create a controller object for jsGrid
			loadData: function(filterItem) { // Load GETs jsonURL
				var d = $.Deferred();
				$.ajax({
					url: jsonURL,
					dataType: "json"
				}).done(
					function(loadData) { // Return has status = 0 for success
						if (loadData.status != 0) {
							$.notify(loadData.message);
							d.resolve();
						}
						else {
							var items = loadData.data.filter(
								makeFilter(filterItem, fieldDescriptions));
							d.resolve(items)
						}
					});
				return d.promise();
			},
			insertItem: function(item) {
				var d = $.Deferred();
				item.Id = 0; // Insert POSTs new item with ID == 0
				postItemChange(jsonURL, item, d);
				return d.promise();
			},
			updateItem: function(item) {
				var d = $.Deferred(); // Update POSTs modified item (same ID)
				postItemChange(jsonURL, item, d);
				return d.promise();
			},
			deleteItem: function(item) {
				var d = $.Deferred(); // Delete POSTs item with negative ID
				if (item.Id) {
					item.Id = -item.Id
				};
				postItemChange(jsonURL, item, d);
				return d.promise();
			},
		};
	};
	playerStatLinkTemplate = function(value, item) {
		return $('<a>').attr('href', base + 'playerStats/' + item.Id)
			.text(item.Name)
	};
})();
