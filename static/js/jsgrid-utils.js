(function() {
    updateFlagImage = function (updateObj, countries) {
	var newFlag = countries.find( // Find country ID countries array
	    function (country) {return country.Id == updateObj.item.Country})
	    .Flag_Image;
	updateObj.item['Flag'] = newFlag;
	$(updateObj.row).find("td.FlagImage").html(newFlag);
    };
    makeFilter = function(filterItem, fieldDescriptions) {
	return function(item) { // Create a function to filter items based on
	    var keep = true; // user's filter parameters and field types
	    for (field in fieldDescriptions) {
		var fd = fieldDescriptions[field];
		if (filterItem[field] && ( // Only check visible fields
		    !fd.hasOwnProperty("visible") || fd.visible)) {
		    if ((["number", "checkbox", "select"].indexOf(fd.type) > -1
			 && item[field] != filterItem[field]) ||
			(fd.type == "text" && 
			 item[field].toLowerCase().indexOf(
			     filterItem[field].toLowerCase()) == -1) ) {
			keep = false;
			break;  // Once a filter fails, quit loop
		    }
		}
	    };
	    return keep
	}
    };
    makeController = function(jsonURL, fieldDescriptions) {
	return { // Create a controller object for jsGrid
	    loadData: function(filterItem) { // Load GETs jsonURL
		var d = $.Deferred();
		$.ajax({url: jsonURL, dataType: "json"}).done(
		    function(loadData) { // Return has status = 0 for success
			if (loadData.status != 0) {
			    $.notify(loadData.message);
			    d.resolve();
			} else { var items = loadData.data.filter(
			    makeFilter(filterItem, fieldDescriptions));
			       d.resolve(items) }
		    });
		return d.promise();
	    },	     
	    insertItem: function(item) {
		var d = $.Deferred();
		item.Id = 0;  // Insert POSTs new item with ID == 0
		$.post(jsonURL, {item: JSON.stringify(item)}, 
		       function(resp) {
			   if (resp.status != 0) { $.notify(resp.message) };
			   d.resolve(item ? resp.status == 0 : null);
		       }, "json");
		return d.promise();
	    },
	    updateItem: function(item) {
		var d = $.Deferred(); // Update POSTs modified item (same ID)
		$.post(jsonURL, {item: JSON.stringify(item)}, 
		       function(resp) {
			   if (resp.status != 0) {$.notify(resp.message) };
			   d.resolve(item ? resp.status == 0 : null);
		       }, "json");
		return d.promise();
	    },
	    deleteItem: function(item) {
		var d = $.Deferred(); // Delete POSTs item with negative ID
		if (item.Id) {item.Id = - item.Id};
		$.post(jsonURL, {item: JSON.stringify(item)}, 
		       function(resp) {
			   if (resp.status != 0) { $.notify(resp.message) };
			   d.resolve(item ? resp.status == 0 : null);
		       }, "json");
		return d.promise();
	    },
	};
    };
})();
